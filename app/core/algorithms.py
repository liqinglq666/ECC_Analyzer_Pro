import numpy as np
from scipy.integrate import simpson
from scipy.signal import savgol_filter

from app.core.physics import MaterialConstants
from app.core.validators import validate_and_sort_data


class BaseAnalyzer:
    def __init__(self, strain_arr, stress_arr):
        raw_strain = np.asarray(strain_arr, dtype=float).ravel()
        raw_stress = np.asarray(stress_arr, dtype=float).ravel()
        raw_strain = self._normalize_strain_units(raw_strain)

        if len(raw_stress) <= 3:
            self.raw_strain = raw_strain
            self.raw_stress = raw_stress
            self.smooth_stress = raw_stress.copy()
            return

        strain, stress = validate_and_sort_data(raw_strain, raw_stress)
        self.raw_strain = strain
        self.raw_stress = stress
        self.smooth_stress = self._smooth_stress(stress)

    @staticmethod
    def _normalize_strain_units(strain: np.ndarray) -> np.ndarray:
        if strain.size == 0:
            return strain

        unit = str(getattr(MaterialConstants, "STRAIN_UNIT", "auto")).lower().strip()
        finite = strain[np.isfinite(strain)]
        max_abs = float(np.max(np.abs(finite))) if finite.size else 0.0

        if unit in {"percent", "%"}:
            return strain / 100.0
        if unit in {"decimal", "absolute", "ratio"}:
            return strain

        threshold = float(getattr(MaterialConstants, "STRAIN_PERCENT_THRESHOLD", 0.2))
        return strain / 100.0 if max_abs > threshold else strain

    @staticmethod
    def _smooth_stress(stress: np.ndarray) -> np.ndarray:
        win = int(getattr(MaterialConstants, "SMOOTH_WINDOW", 15))
        poly = int(getattr(MaterialConstants, "SMOOTH_POLY", 3))
        if win % 2 == 0:
            win += 1
        win = max(3, win)
        if len(stress) > win and win > poly:
            try:
                return savgol_filter(stress, window_length=win, polyorder=poly)
            except ValueError:
                pass
        return stress.copy()

    def _calc_peak_robust(self) -> tuple:
        if len(self.raw_stress) == 0:
            return None, float("nan"), float("nan")
        idx_peak = int(np.argmax(self.smooth_stress))
        return idx_peak, float(self.smooth_stress[idx_peak]), float(self.raw_strain[idx_peak])

    def _calc_E_effective_regression(self, idx_peak: int | None, stress_max: float) -> tuple:
        if idx_peak is None or len(self.raw_stress) < 5 or not np.isfinite(stress_max) or stress_max <= 0 or idx_peak <= 2:
            return float("nan"), float("nan")

        lower = float(getattr(MaterialConstants, "ELASTIC_LOWER_RATIO", 0.10))
        upper = float(getattr(MaterialConstants, "ELASTIC_UPPER_RATIO", 0.40))
        if upper <= lower:
            lower, upper = 0.10, 0.40

        stress_seg = self.raw_stress[:idx_peak]
        strain_seg = self.raw_strain[:idx_peak]
        mask = (stress_seg >= lower * stress_max) & (stress_seg <= upper * stress_max)
        x_fit = strain_seg[mask]
        y_fit = stress_seg[mask]

        if len(x_fit) < 3:
            mask = (stress_seg >= 0.05 * stress_max) & (stress_seg <= 0.50 * stress_max)
            x_fit = strain_seg[mask]
            y_fit = stress_seg[mask]

        if len(x_fit) < 3:
            return float("nan"), float("nan")

        try:
            slope, intercept = np.polyfit(x_fit, y_fit, 1)
        except (TypeError, ValueError, np.linalg.LinAlgError):
            return float("nan"), float("nan")
        return (float(slope), float(intercept)) if slope > 0 else (float("nan"), float("nan"))

    def _calc_tangent_modulus_curve(self, idx_peak):
        if idx_peak is None or idx_peak < 5:
            return np.array([], dtype=float)

        s_strain = self.raw_strain[:idx_peak]
        s_stress = self.smooth_stress[:idx_peak]
        with np.errstate(divide="ignore", invalid="ignore"):
            dedx = np.gradient(s_stress, s_strain)
            dedx = np.where(np.isfinite(dedx), dedx, np.nan)

        win = max(5, len(dedx) // 10)
        if win % 2 == 0:
            win += 1
        if len(dedx) > win:
            try:
                return savgol_filter(dedx, win, 2)
            except ValueError:
                pass
        return dedx

    def _calc_E_init_statistical(self, dedx_curve):
        if len(dedx_curve) == 0:
            return float("nan")

        search_ratio = float(getattr(MaterialConstants, "INITIAL_MODULUS_SEARCH_LIMIT", 0.15))
        top_ratio = float(getattr(MaterialConstants, "INITIAL_MODULUS_PERCENTILE", 0.10))
        limit_idx = max(5, int(len(dedx_curve) * search_ratio))
        sub_curve = dedx_curve[:limit_idx]
        valid_slopes = sub_curve[np.isfinite(sub_curve) & (sub_curve > 1000) & (sub_curve < 60000)]
        if len(valid_slopes) == 0:
            return float("nan")

        sorted_slopes = np.sort(valid_slopes)[::-1]
        top_n = max(1, int(len(sorted_slopes) * top_ratio))
        return float(np.mean(sorted_slopes[:top_n]))


class TensileAnalyzer(BaseAnalyzer):
    def run_analysis(self) -> dict:
        idx_peak, stress_max, strain_at_peak = self._calc_peak_robust()
        E_eff, intercept = self._calc_E_effective_regression(idx_peak, stress_max)

        dedx = self._calc_tangent_modulus_curve(idx_peak)
        E_init = self._calc_E_init_statistical(dedx)
        if np.isfinite(E_eff) and (not np.isfinite(E_init) or E_init < E_eff):
            E_init = E_eff

        idx_cr = None
        sigma_cr = float("nan")
        crack_status = "not_detected"
        len_calc = min(len(dedx), idx_peak or 0)
        if len_calc > 0 and np.isfinite(E_eff) and E_eff > 0:
            y_theory = E_eff * self.raw_strain[:len_calc] + intercept
            dev = y_theory - self.raw_stress[:len_calc]

            tol_base = float(getattr(MaterialConstants, "CRACK_TOLERANCE_BASE", 0.05))
            tol_ratio = float(getattr(MaterialConstants, "CRACK_TOLERANCE_RATIO", 0.01))
            stiffness_ratio = float(getattr(MaterialConstants, "CRACK_STIFFNESS_CONSTRAINT", 0.85))
            min_stress_ratio = float(getattr(MaterialConstants, "CRACK_MIN_STRESS_RATIO", 0.10))

            mask = (
                (dev > max(tol_base, tol_ratio * stress_max))
                & np.isfinite(dedx[:len_calc])
                & (dedx[:len_calc] < stiffness_ratio * E_init)
                & (self.raw_stress[:len_calc] > min_stress_ratio * stress_max)
            )
            candidates = np.where(mask)[0]
            if len(candidates):
                idx_cr = int(candidates[0])
                sigma_cr = float(self.raw_stress[idx_cr])
                crack_status = "detected"

        ratio_u = float(getattr(MaterialConstants, "ULTIMATE_STRAIN_RATIO", 0.85))
        threshold_u = ratio_u * stress_max if np.isfinite(stress_max) else float("nan")
        idx_u = idx_peak

        if idx_peak is not None and len(self.raw_stress) > idx_peak + 5:
            look_ahead = max(10, int(len(self.raw_stress) * 0.02))
            for i in range(idx_peak, len(self.smooth_stress)):
                if self.smooth_stress[i] < threshold_u:
                    future_segment = self.smooth_stress[i:i + look_ahead]
                    if len(future_segment) and np.max(future_segment) < threshold_u:
                        idx_u = int(i)
                        break
            else:
                idx_u = len(self.raw_stress) - 1

        epsilon_u = float(self.raw_strain[idx_u]) if idx_u is not None and len(self.raw_strain) else float("nan")

        energy = float("nan")
        if idx_u is not None:
            mask_e = np.arange(len(self.raw_strain)) <= idx_u
            if np.sum(mask_e) > 2:
                try:
                    energy = max(0.0, float(simpson(y=self.raw_stress[mask_e], x=self.raw_strain[mask_e]) * 1000.0))
                except (TypeError, ValueError):
                    pass

        if idx_cr is None or not np.isfinite(epsilon_u):
            sh_cap = float("nan")
            cv = float("nan")
        else:
            eps_fc = float(self.raw_strain[idx_cr])
            sh_cap = max(0.0, epsilon_u - eps_fc)
            cv = float("nan")
            if idx_u is not None and idx_u > idx_cr + 1:
                plateau = self.raw_stress[idx_cr:idx_u]
                mean_plateau = float(np.mean(plateau))
                if mean_plateau > 1e-6:
                    cv = float(np.std(plateau) / mean_plateau)

        return {
            "Type": "Tensile",
            "E_eff (GPa)": E_eff / 1000.0,
            "E_init (GPa)": E_init / 1000.0,
            "First Crack Strength (MPa)": sigma_cr,
            "Ultimate Stress (MPa)": float(stress_max),
            "Peak Strain (%)": float(strain_at_peak) * 100.0,
            "Ultimate Strain (%)": epsilon_u * 100.0,
            "Strain Energy (kJ/m³)": energy,
            "Fracture Energy (kJ/m²)": energy * (float(MaterialConstants.GAUGE_LENGTH_MM) / 1000.0),
            "Hardening Capacity (%)": sh_cap * 100.0,
            "Plateau Stability (CV)": cv,
            "First Crack Status": crack_status,
            "_idx_peak": idx_peak,
            "_idx_cr": idx_cr,
            "_idx_u": idx_u,
            "_E_intercept": float(intercept),
        }


class CompressiveAnalyzer(BaseAnalyzer):
    def __init__(self, strain_arr, stress_arr):
        super().__init__(strain_arr, stress_arr)
        if bool(getattr(MaterialConstants, "COMPRESSIVE_STRESS_ABS", True)):
            self.raw_stress = np.abs(self.raw_stress)
            self.smooth_stress = np.abs(self.smooth_stress)

    def run_analysis(self) -> dict:
        if len(self.raw_stress) <= 1:
            value = float(self.raw_stress[0]) if len(self.raw_stress) else float("nan")
            return {
                "Type": "Compressive",
                "E_eff (GPa)": float("nan"),
                "Peak Stress (MPa)": value,
                "Peak Strain (%)": float("nan"),
                "_idx_peak": 0 if len(self.raw_stress) else None,
                "_idx_cr": None,
                "_idx_u": 0 if len(self.raw_stress) else None,
            }

        idx_peak, sigma_peak, strain_peak = self._calc_peak_robust()
        E_sec = float("nan")
        if idx_peak is not None and idx_peak > 0:
            target = sigma_peak * 0.3
            idx_30 = int(np.abs(self.raw_stress[:idx_peak] - target).argmin())
            s30 = float(self.raw_stress[idx_30])
            e30 = float(self.raw_strain[idx_30])
            if e30 > 1e-6:
                E_sec = s30 / e30

        return {
            "Type": "Compressive",
            "E_eff (GPa)": E_sec / 1000.0,
            "Peak Stress (MPa)": float(sigma_peak),
            "Peak Strain (%)": float(strain_peak) * 100.0,
            "_idx_peak": idx_peak,
            "_idx_cr": None,
            "_idx_u": idx_peak,
        }
