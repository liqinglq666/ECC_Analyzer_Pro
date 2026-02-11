import numpy as np
from scipy.signal import savgol_filter
from scipy.integrate import simpson
from app.core.physics import MaterialConstants

# Fallback validator
try:
    from app.core.validators import validate_and_sort_data
except ImportError:
    def validate_and_sort_data(strain, stress):
        mask = ~np.isnan(strain) & ~np.isnan(stress)
        s, st = strain[mask], stress[mask]
        indices = np.argsort(s)
        return s[indices], st[indices]


class BaseAnalyzer:
    def __init__(self, strain_arr, stress_arr):
        raw_strain = np.asarray(strain_arr, dtype=float)
        raw_stress = np.asarray(stress_arr, dtype=float)

        # [Compressive Fix] 针对抗压单点数据的“直通车”
        # 如果数据点极少，直接保留原值，跳过平滑和排序，防止数据丢失
        if len(raw_stress) <= 3:
            self.raw_strain = raw_strain
            self.raw_stress = raw_stress
            self.smooth_stress = raw_stress.copy()
            return

        # --- 标准曲线处理流程 ---
        strain, stress = validate_and_sort_data(raw_strain, raw_stress)

        # 智能单位判断 (若最大应变 > 1.0，视为百分比，转换为绝对值)
        if np.nanmax(strain) > 1.0:
            self.raw_strain = strain / 100.0
        else:
            self.raw_strain = strain
        self.raw_stress = stress

        # 平滑处理 (Savitzky-Golay 滤波)
        win = MaterialConstants.SMOOTH_WINDOW
        if win % 2 == 0: win += 1
        if len(stress) > win:
            try:
                self.smooth_stress = savgol_filter(stress, window_length=win, polyorder=3)
            except:
                self.smooth_stress = stress.copy()
        else:
            self.smooth_stress = stress.copy()

    def _calc_peak_robust(self) -> tuple:
        if len(self.raw_stress) == 0: return 0, 0.0, 0.0
        idx_peak = np.argmax(self.smooth_stress)
        return idx_peak, self.smooth_stress[idx_peak], self.raw_strain[idx_peak]

    def _calc_E_effective_regression(self, idx_peak: int, stress_max: float) -> tuple:
        """计算有效弹性模量 (区间回归法)"""
        if len(self.raw_stress) < 5 or stress_max <= 0: return 0.0, 0.0

        limit_lower = MaterialConstants.ELASTIC_LOWER_RATIO * stress_max
        limit_upper = MaterialConstants.ELASTIC_UPPER_RATIO * stress_max

        strain_seg = self.raw_strain[:idx_peak]
        stress_seg = self.raw_stress[:idx_peak]
        mask = (stress_seg >= limit_lower) & (stress_seg <= limit_upper)

        x_fit = strain_seg[mask]
        y_fit = stress_seg[mask]

        # 如果区间内点太少，放宽范围
        if len(x_fit) < 3:
            mask = (stress_seg >= stress_max * 0.05) & (stress_seg <= stress_max * 0.5)
            x_fit, y_fit = strain_seg[mask], stress_seg[mask]

        if len(x_fit) > 2:
            try:
                slope, intercept = np.polyfit(x_fit, y_fit, 1)
                return max(0.0, slope), intercept
            except:
                return 0.0, 0.0
        return 0.0, 0.0

    def _calc_tangent_modulus_curve(self, idx_peak):
        if idx_peak < 5: return np.zeros(idx_peak)
        s_strain = self.raw_strain[:idx_peak]
        s_stress = self.smooth_stress[:idx_peak]
        with np.errstate(divide='ignore', invalid='ignore'):
            dedx = np.gradient(s_stress, s_strain)
            dedx = np.nan_to_num(dedx, nan=0.0)
        try:
            win = max(5, len(dedx) // 10);
            if win % 2 == 0: win += 1
            return savgol_filter(dedx, win, 2)
        except:
            return dedx

    def _calc_E_init_statistical(self, dedx_curve):
        """
        [Scientific Optimization] 初始模量计算
        增加了物理阈值过滤，防止出现 300 GPa 这种非物理数值
        """
        if len(dedx_curve) == 0: return 0.0

        # 仅搜索前 30% 的数据
        limit_idx = max(5, int(len(dedx_curve) * 0.3))
        sub_curve = dedx_curve[:limit_idx]

        # [Fix] 物理过滤:
        # 下限 1000 (1 GPa): 过滤噪音
        # 上限 60000 (60 GPa): 混凝土/ECC 类材料的物理极限，过滤试验机刚度伪影
        valid_slopes = sub_curve[(sub_curve > 1000) & (sub_curve < 60000)]

        if len(valid_slopes) == 0:
            # 如果没有合法的初始模量，返回 0 (后续逻辑会退化使用 E_eff)
            return 0.0

        # 取最大的前 10% 的平均值
        sorted_slopes = np.sort(valid_slopes)[::-1]
        return np.mean(sorted_slopes[:max(1, int(len(sorted_slopes) * 0.1))])


class TensileAnalyzer(BaseAnalyzer):
    def run_analysis(self) -> dict:
        idx_peak, stress_max, strain_at_peak = self._calc_peak_robust()
        E_eff, intercept = self._calc_E_effective_regression(idx_peak, stress_max)

        # 1. 弹性模量逻辑
        dedx = self._calc_tangent_modulus_curve(idx_peak)
        E_init = self._calc_E_init_statistical(dedx)
        # 物理兜底：如果算出的 E_init 依然为0或小于 E_eff，则认为 E_eff 更可靠
        if E_init < E_eff: E_init = E_eff

        # 2. 首裂强度 (双判据)
        len_calc = min(len(dedx), idx_peak)
        if len_calc > 0:
            y_theory = E_eff * self.raw_strain[:len_calc] + intercept
            dev = y_theory - self.raw_stress[:len_calc]
            mask = (dev > max(0.05, 0.01 * stress_max)) & (dedx[:len_calc] < 0.85 * E_init) & (
                        self.raw_stress[:len_calc] > 0.1 * stress_max)
            candidates = np.where(mask)[0]
            sigma_cr, idx_cr = (self.raw_stress[candidates[0]], candidates[0]) if len(candidates) > 0 else (
            stress_max, idx_peak)
        else:
            sigma_cr, idx_cr = stress_max, idx_peak

        # 3. 极限状态 (抗锯齿优化)
        # Look-Ahead 机制：防止因 ECC 曲线震荡而过早判定失效
        ratio_u = getattr(MaterialConstants, "ULTIMATE_STRAIN_RATIO", 0.85)
        threshold_u = ratio_u * stress_max
        idx_u = idx_peak

        if len(self.raw_stress) > idx_peak + 5:
            # 向后看 2% 的数据长度
            look_ahead = max(10, int(len(self.raw_stress) * 0.02))

            for i in range(idx_peak, len(self.smooth_stress)):
                if self.smooth_stress[i] < threshold_u:
                    # 检查未来一段是否反弹
                    future_segment = self.smooth_stress[i: i + look_ahead]
                    if len(future_segment) > 0 and np.max(future_segment) < threshold_u:
                        idx_u = i
                        break
            else:
                idx_u = len(self.raw_stress) - 1

        epsilon_u = self.raw_strain[idx_u]

        # 4. 能量计算
        try:
            mask_e = (np.arange(len(self.raw_strain)) <= idx_u)
            energy = simpson(y=self.raw_stress[mask_e], x=self.raw_strain[mask_e]) * 1000.0 if np.sum(
                mask_e) > 2 else 0.0
        except:
            energy = 0.0

        # 5. 高级指标 (CV 优化)
        eps_fc = self.raw_strain[idx_cr]
        sh_cap = max(0, epsilon_u - eps_fc)

        cv = 0.0
        # [Fix] 放宽 CV 计算门槛，只要硬化段大于 1 个点就计算
        if idx_u > idx_cr + 1:
            plat = self.raw_stress[idx_cr:idx_u]
            mean_p = np.mean(plat)
            if mean_p > 1e-6:
                cv = np.std(plat) / mean_p

        return {
            "Type": "Tensile",
            "E_eff (GPa)": E_eff / 1000.0,
            "E_init (GPa)": E_init / 1000.0,
            "First Crack Strength (MPa)": sigma_cr,
            "Ultimate Stress (MPa)": stress_max,
            "Ultimate Strain (%)": epsilon_u * 100.0,
            "Strain Energy (kJ/m³)": energy,
            "Fracture Energy (kJ/m²)": energy * (MaterialConstants.GAUGE_LENGTH_MM / 1000.0),
            "Hardening Capacity (%)": sh_cap * 100.0,
            "Plateau Stability (CV)": cv,
            "_idx_peak": int(idx_peak),
            "_idx_cr": int(idx_cr),
            "_idx_u": int(idx_u),
            "_E_intercept": intercept
        }


class CompressiveAnalyzer(BaseAnalyzer):
    def run_analysis(self) -> dict:
        """抗压分析"""
        # 情况 1: 单点数据
        if len(self.raw_stress) <= 1:
            val = self.raw_stress[0] if len(self.raw_stress) > 0 else 0.0
            return {
                "Type": "Compressive",
                "E_eff (GPa)": 0.0,
                "Peak Stress (MPa)": float(val),
                "Peak Strain (%)": 0.0,
                "_idx_peak": 0, "_idx_cr": 0, "_idx_u": 0
            }

        # 情况 2: 完整曲线
        idx_peak, sigma_peak, strain_peak = self._calc_peak_robust()
        try:
            target = sigma_peak * 0.3
            idx_30 = (np.abs(self.raw_stress[:idx_peak] - target)).argmin()
            s30 = self.raw_stress[idx_30]
            e30 = self.raw_strain[idx_30]
            E_sec = (s30 / e30) if e30 > 1e-6 else 0.0
        except:
            E_sec = 0.0

        return {
            "Type": "Compressive",
            "E_eff (GPa)": E_sec / 1000.0,
            "Peak Stress (MPa)": sigma_peak,
            "Peak Strain (%)": strain_peak * 100.0,
            "_idx_peak": int(idx_peak), "_idx_cr": 0, "_idx_u": int(idx_peak)
        }