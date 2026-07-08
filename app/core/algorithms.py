import numpy as np
from scipy.signal import savgol_filter
from scipy.integrate import simpson
from app.core.physics import MaterialConstants

try:
    from app.core.validators import validate_and_sort_data
except ImportError:
    def validate_and_sort_data(strain, stress):
        strain = np.asarray(strain, dtype=float).ravel()
        stress = np.asarray(stress, dtype=float).ravel()
        mask = np.isfinite(strain) & np.isfinite(stress)
        strain, stress = strain[mask], stress[mask]
        indices = np.argsort(strain)
        return strain[indices], stress[indices]


class BaseAnalyzer:
    """Shared preprocessing for stress-strain analyzers."""

    def __init__(self, strain_arr, stress_arr):
        raw_strain = np.asarray(strain_arr, dtype=float).ravel()
        raw_stress = np.asarray(stress_arr, dtype=float).ravel()
        raw_strain = self._normalize_strain_units(raw_strain)

        # Summary rows such as compressive strength values may contain only one point.
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
        """
        Normalize strain to decimal form.

        Most ECC spreadsheets use percent strain, e.g. 0.5 means 0.5%.
        Some DIC/software exports use decimal strain, e.g. 0.005 means 0.5%.
        The previous max(strain) > 1 rule could misread 0.5% as 50%.
        """
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
        # Auto mode: values above threshold are treated as percent strain.
        # Example: 0.5 -> 0.5% -> 0.005; 0.005 remains decimal strain.
        if max_abs > threshold:
            return strain / 100.0
        return strain

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
            except Exception:
                return stress.copy()
        return stress.copy()

    def _calc_peak_robust(self) -> tuple:
        if len(self.raw_stress) == 0:
            return 0, 0.0, 0.0
        idx_peak = int(np.argmax(self.smooth_stress))
        return idx_peak, float(self.smooth_stress[idx_peak]), float(self.raw_strain[idx_peak])

    def _calc_E_effective_regression(self, idx_peak: int, stress_max: float) -> tuple:
        """Effective modulus from a configurable stress-ratio regression window."""
        if len(self.raw_stress) < 5 or stress_max <= 0 or idx_peak <= 2:
            return 0.0, 0.0

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

        if len(x_fit) > 2:
            try:
                slope, intercept = np.polyfit(x_fit, y_fit, 1)
                return max(0.0, float(slope)), float(intercept)
            except Exception:
                return 0.0, 0.0
        return 0.0, 0.0

    def _calc_tangent_modulus_curve(self, idx_peak):
        if idx_peak < 5:
            return np.zeros(max(0, idx_peak))

        s_strain = self.raw_strain[:idx_peak]
        s_stress = self.smooth_stress[:idx_peak]
        with np.errstate(divide="ignore", invalid="ignore"):
            dedx = np.gradient(s_stress, s_strain)
            dedx = np.nan_to_num(dedx, nan=0.0, posinf=0.0, neginf=0.0)

        try:
            win = max(5, len(dedx) // 10)
            if win % 2 == 0:
                win += 1
            if len(dedx) > win:
                return savgol_filter(dedx, win, 2)
        except Exception:
            pass
        return dedx

    def _calc_E_init_statistical(self, dedx_curve):
        """Initial modulus from high but physically bounded early tangent slopes."""
        if len(dedx_curve) == 0:
            return 0.0

        search_ratio = float(getattr(MaterialConstants, "INITIAL_MODULUS_SEARCH_LIMIT", 0.15))
        top_ratio = float(getattr(MaterialConstants, "INITIAL_MODULUS_PERCENTILE", 0.10))
        limit_idx = max(5, int(len(dedx_curve) * search_ratio))
        sub_curve = dedx_curve[:limit_idx]

        valid_slopes = sub_curve[(sub_curve > 1000) & (sub_curve < 60000)]
        if len(valid_slopes) == 0:
            return 0.0

        sorted_slopes = np.sort(valid_slopes)[::-1]
        top_n = max(1, int(len(sorted_slopes) * top_ratio))
        return float(np.mean(sorted_slopes[:top_n]))


class TensileAnalyzer(BaseAnalyzer):
    def run_analysis(self) -> dict:
        idx_peak, stress_max, strain_at_peak = self._calc_peak_robust()
        E_eff, intercept = self._calc_E_effective_regression(idx_peak, stress_max)

        dedx = self._calc_tangent_modulus_curve(idx_peak)
        E_init = self._calc_E_init_statistical(dedx)
        if E_init < E_eff:
            E_init = E_eff

        len_calc = min(len(dedx), idx_peak)
        if len_calc > 0 and E_eff > 0:
            y_theory = E_eff * self.raw_strain[:len_calc] + intercept
            dev = y_theory - self.raw_stress[:len_calc]

            tol_base = float(getattr(MaterialConstants, "CRACK_TOLERANCE_BASE", 0.05))
            tol_ratio = float(getattr(MaterialConstants, "CRACK_TOLERANCE_RATIO", 0.01))
            stiffness_ratio = float(getattr(MaterialConstants, "CRACK_STIFFNESS_CONSTRAINT", 0.85))
            min_stress_ratio = float(getattr(MaterialConstants, "CRACK_MIN_STRESS_RATIO", 0.10))

            mask = (
                (dev > max(tol_base, tol_ratio * stress_max))
                & (dedx[:len_calc] < stiffness_ratio * E_init)
                & (self.raw_stress[:len_calc] > min_stress_ratio * stress_max)
            )
            candidates = np.where(mask)[0]
            if len(candidates) > 0:
                idx_cr = int(candidates[0])
                sigma_cr = float(self.raw_stress[idx_cr])
            else:
                idx_cr = int(idx_peak)
                sigma_cr = float(stress_max)
        else:
            idx_cr = int(idx_peak)
            sigma_cr = float(stress_max)

        ratio_u = float(getattr(MaterialConstants, "ULTIMATE_STRAIN_RATIO", 0.85))
        threshold_u = ratio_u * stress_max
        idx_u = int(idx_peak)

        if len(self.raw_stress) > idx_peak + 5:
            look_ahead = max(10, int(len(self.raw_stress) * 0.02))
            for i in range(idx_peak, len(self.smooth_stress)):
                if self.smooth_stress[i] < threshold_u:
                    future_segment = self.smooth_stress[i:i + look_ahead]
                    if len(future_segment) > 0 and np.max(future_segment) < threshold_u:
                        idx_u = int(i)
                        break
            else:
                idx_u = len(self.raw_stress) - 1

        epsilon_u = float(self.raw_strain[idx_u]) if len(self.raw_strain) else 0.0

        try:
            mask_e = np.arange(len(self.raw_strain)) <= idx_u
            energy = simpson(y=self.raw_stress[mask_e], x=self.raw_strain[mask_e]) * 1000.0 if np.sum(mask_e) > 2 else 0.0
            energy = max(0.0, float(energy))
        except Exception:
            energy = 0.0

        eps_fc = float(self.raw_strain[idx_cr]) if len(self.raw_strain) else 0.0
        sh_cap = max(0.0, epsilon_u - eps_fc)

        cv = 0.0
        if idx_u > idx_cr + 1:
            plat = self.raw_stress[idx_cr:idx_u]
            mean_p = float(np.mean(plat))
            if mean_p > 1e-6:
                cv = float(np.std(plat) / mean_p)

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
            "_idx_peak": int(idx_peak),
            "_idx_cr": int(idx_cr),
            "_idx_u": int(idx_u),
            "_E_intercept": float(intercept),
        }


class CompressiveAnalyzer(BaseAnalyzer):
    def __init__(self, strain_arr, stress_arr):
        super().__init__(strain_arr, stress_arr)
        if bool(getattr(MaterialConstants, "COMPRESSIVE_STRESS_ABS", True)):
            self.raw_stress = np.abs(self.raw_stress)
            self.smooth_stress = np.abs(self.smooth_stress)

    def run_analysis(self) -> dict:
        """Compressive strength/modulus analysis."""
        if len(self.raw_stress) <= 1:
            val = float(self.raw_stress[0]) if len(self.raw_stress) > 0 else 0.0
            return {
                "Type": "Compressive",
                "E_eff (GPa)": 0.0,
                "Peak Stress (MPa)": val,
                "Peak Strain (%)": 0.0,
                "_idx_peak": 0,
                "_idx_cr": 0,
                "_idx_u": 0,
            }

        idx_peak, sigma_peak, strain_peak = self._calc_peak_robust()
        try:
            if idx_peak <= 0:
                E_sec = 0.0
            else:
                target = sigma_peak * 0.3
                idx_30 = int(np.abs(self.raw_stress[:idx_peak] - target).argmin())
                s30 = float(self.raw_stress[idx_30])
                e30 = float(self.raw_strain[idx_30])
                E_sec = (s30 / e30) if e30 > 1e-6 else 0.0
        except Exception:
            E_sec = 0.0

        return {
            "Type": "Compressive",
            "E_eff (GPa)": E_sec / 1000.0,
            "Peak Stress (MPa)": float(sigma_peak),
            "Peak Strain (%)": float(strain_peak) * 100.0,
            "_idx_peak": int(idx_peak),
            "_idx_cr": 0,
            "_idx_u": int(idx_peak),
        }
