import pandas as pd
import numpy as np
import traceback
from pathlib import Path
from typing import List, Dict, Any


class DataExporter:
    """
    ECC 导出模块 V20.7 (科研符号适配版)
    - Feature: Excel 表头自动映射为 Unicode 科学符号 (σ_cr, ε_tu 等)
    - Tensile: Raw Data (智能列对齐 + 降维保护) + 详细分层报表
    - Compressive: 智能分组统计 (优先识别 Sample ID)
    """

    # 内部键名 -> Excel 科学表头映射
    SCIENTIFIC_HEADER_MAP = {
        # Tensile
        "E_eff (GPa)": "E_eff (GPa)",
        "First Crack Strength (MPa)": "σ_cr (MPa)",
        "Ultimate Stress (MPa)": "σ_u (MPa)",
        "Ultimate Strain (%)": "ε_tu (%)",
        "E_init (GPa)": "E_init (GPa)",
        "Strain Energy (kJ/m³)": "E_v (kJ/m³)",
        "Fracture Energy (kJ/m²)": "G_F (kJ/m²)",
        "Hardening Capacity (%)": "Δε_sh (%)",
        "Plateau Stability (CV)": "CV_σ",
        # Compressive
        "Mean Strength (MPa)": "σ_mean (MPa)",
        "Standard Deviation": "SD (MPa)",
        "Sample Count": "N"
    }

    @staticmethod
    def export_excel(checked_data: List[Dict[str, Any]], filepath: Path):
        """
        主导出入口
        :param checked_data: 包含计算结果的字典列表
        :param filepath: 保存路径
        """
        if not checked_data: return

        # 1. 自动检测模式
        is_tensile = True
        for item in checked_data:
            if item.get("Type") == "Compressive":
                is_tensile = False
                break

        # 2. 预排序: 按文件名 -> 样品名排序
        sorted_items = sorted(checked_data, key=lambda x: (str(x.get("Source File", "")), str(x.get("Sample ID", ""))))

        try:
            # 确保父目录存在
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:

                # ==========================================
                # 分支 A: 抗拉模式 (Tensile)
                # ==========================================
                if is_tensile:
                    # A.1 Raw Data Sheet
                    df_raw = DataExporter._make_tensile_raw_df(sorted_items)
                    if not df_raw.empty:
                        df_raw.to_excel(writer, sheet_name='Raw Data (Curves)', index=False)

                    # A.2 Analysis Report Sheet
                    # 定义输出列顺序（内部键名）
                    cols = [
                        "E_eff (GPa)", "First Crack Strength (MPa)", "Ultimate Stress (MPa)", "Ultimate Strain (%)",
                        "E_init (GPa)", "Strain Energy (kJ/m³)", "Fracture Energy (kJ/m²)",
                        "Hardening Capacity (%)", "Plateau Stability (CV)"
                    ]
                    df_summary = DataExporter._make_detailed_tensile_summary(sorted_items, cols)

                    # [Optimization] 应用科学符号映射
                    df_summary.rename(columns=DataExporter.SCIENTIFIC_HEADER_MAP, inplace=True)

                    df_summary.to_excel(writer, sheet_name='Tensile Analysis', index=False)

                # ==========================================
                # 分支 B: 抗压模式 (Compressive)
                # ==========================================
                else:
                    df_compressive = DataExporter._make_compressive_summary(sorted_items)

                    # [Optimization] 应用科学符号映射
                    df_compressive.rename(columns=DataExporter.SCIENTIFIC_HEADER_MAP, inplace=True)

                    df_compressive.to_excel(writer, sheet_name='Compressive Strength', index=False)

        except PermissionError:
            print("Export Failed: Permission denied. Please close the Excel file first.")
        except Exception:
            # 打印完整堆栈，便于调试
            traceback.print_exc()

    # ---------------------------------------------------------
    # 内部逻辑实现
    # ---------------------------------------------------------

    @staticmethod
    def _make_tensile_raw_df(data_list: List[Dict]) -> pd.DataFrame:
        """[抗拉] 组装原始曲线数据"""
        raw_dict = {}
        max_len = 0

        arrays = []
        for item in data_list:
            strain = item.get("raw_strain")
            stress = item.get("raw_stress")
            name = str(item.get("Sample ID", "Sample")).strip()

            if strain is not None and stress is not None and len(strain) > 0:
                # [Fix] 强制降维，防止 (N,1) 数组导致格式错误
                strain = np.array(strain).flatten()
                stress = np.array(stress).flatten()

                # 智能单位转换
                s_pct = strain * 100 if np.max(strain) < 2.0 else strain

                # 构建列名
                col_strain = f"{name} - ε (%)"
                col_stress = f"{name} - σ (MPa)"

                arrays.append((col_strain, s_pct))
                arrays.append((col_stress, stress))

                if len(s_pct) > max_len: max_len = len(s_pct)

        # 补齐数据
        for col_name, arr in arrays:
            if len(arr) < max_len:
                padded = np.pad(arr, (0, max_len - len(arr)), constant_values=np.nan)
                raw_dict[col_name] = padded
            else:
                raw_dict[col_name] = arr

        return pd.DataFrame(raw_dict)

    @staticmethod
    def _make_detailed_tensile_summary(data_list: List[Dict], value_keys: List[str]) -> pd.DataFrame:
        """[抗拉] 生成详细分层报表"""
        final_rows = []

        # 按 Source File 分组
        groups = {}
        for item in data_list:
            fname = item.get("Source File", "Unknown Group")
            if fname not in groups: groups[fname] = []
            groups[fname].append(item)

        for fname, items in groups.items():
            group_vals = {k: [] for k in value_keys}

            # 1. 填入个体数据
            for item in items:
                row = {
                    "Group / File": fname,
                    "Sample ID": item.get("Sample ID", "")
                }
                for k in value_keys:
                    val = item.get(k, None)
                    if val is not None and isinstance(val, (int, float)):
                        row[k] = val
                        group_vals[k].append(val)
                    else:
                        row[k] = val
                final_rows.append(row)

            # 2. 计算统计行
            if len(items) > 1:
                avg_row = {"Group / File": fname, "Sample ID": "AVG (Mean)"}
                sd_row = {"Group / File": fname, "Sample ID": "SD (Stdev)"}
                cv_row = {"Group / File": fname, "Sample ID": "COV (%)"}

                for k in value_keys:
                    vals = np.array(group_vals[k], dtype=float)
                    vals = vals[~np.isnan(vals)]

                    if len(vals) > 0:
                        mean_val = np.mean(vals)
                        std_val = np.std(vals, ddof=1) if len(vals) > 1 else 0.0

                        avg_row[k] = mean_val
                        sd_row[k] = std_val
                        cv_row[k] = (std_val / mean_val * 100) if abs(mean_val) > 1e-9 else 0.0

                final_rows.append(avg_row)
                final_rows.append(sd_row)
                final_rows.append(cv_row)

            final_rows.append({"Sample ID": ""})

        return pd.DataFrame(final_rows)

    @staticmethod
    def _make_compressive_summary(data_list: List[Dict]) -> pd.DataFrame:
        """[抗压] 生成精简统计表"""
        if not data_list: return pd.DataFrame()

        clean_data = []
        for item in data_list:
            group_name = str(item.get("Sample ID", "")).strip()
            if not group_name:
                group_name = str(item.get("Source File", "Unknown")).strip()

            try:
                stress = float(item.get("Peak Stress (MPa)", 0))
                clean_data.append({"Group": group_name, "Stress": stress})
            except (ValueError, TypeError):
                continue

        df = pd.DataFrame(clean_data)
        if df.empty: return pd.DataFrame()

        # 聚合计算
        stats = df.groupby("Group")["Stress"].agg(['count', 'mean', 'std']).reset_index()

        stats['std'] = stats['std'].fillna(0.0)
        stats['COV (%)'] = (stats['std'] / stats['mean'] * 100).fillna(0.0)

        stats.rename(columns={
            "Group": "Sample Group",
            "mean": "Mean Strength (MPa)",
            "std": "Standard Deviation",
            "count": "Sample Count"
        }, inplace=True)

        stats = stats.round(2)
        return stats[["Sample Group", "Mean Strength (MPa)", "Standard Deviation", "COV (%)", "Sample Count"]]