import pandas as pd
import numpy as np
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional


class DataLoader:
    """
    数据加载器 V24.3 (Smart Row Parsing)
    - Fix: 完美适配 "Name Value1 Value2" 这种一行多值的抗压汇总格式。
    - Fix: 智能剔除样品名之前的序号列 (如 "1  FSC-AIR  27.7" 中的 1)。
    """

    @staticmethod
    def load_file_smart(file_path: Path, max_sheets: int = 10, mode: str = "Tensile") -> Tuple[
        Optional[List[Dict]], Optional[str]]:
        all_samples = []
        try:
            ext = file_path.suffix.lower()
            if ext not in ['.xlsx', '.xls', '.csv']:
                return None, f"Unsupported format: {ext}"

            if ext == '.csv':
                try:
                    df = pd.read_csv(file_path, header=None, sep=None, engine='python', on_bad_lines='skip')
                    samples = DataLoader._parse_dataframe(df, mode)
                    for s in samples: s['sheet_name'] = "CSV"
                    all_samples.extend(samples)
                except Exception as e:
                    return None, f"CSV Parse Error: {e}"
            else:
                try:
                    xls = pd.ExcelFile(file_path)
                except:
                    try:
                        xls = pd.ExcelFile(file_path, engine='xlrd')
                    except:
                        return None, "Cannot open Excel file."

                sheet_names = xls.sheet_names[:max_sheets]
                for sheet_name in sheet_names:
                    try:
                        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                        if df.empty: continue
                        samples = DataLoader._parse_dataframe(df, mode)
                        if samples:
                            for s in samples: s['sheet_name'] = sheet_name
                            all_samples.extend(samples)
                    except:
                        continue
                xls.close()

            if len(all_samples) > 0:
                return all_samples, None
            else:
                return None, "No valid data found."

        except Exception as e:
            return None, f"Load Error: {str(e)}"

    @staticmethod
    def _parse_dataframe(df: pd.DataFrame, mode: str) -> List[Dict]:
        df = df.dropna(how='all', axis=0).dropna(how='all', axis=1)

        # 抗压模式：绝大多数情况是汇总表 (Row Summary)
        if "Compressive" in mode:
            samples_row = DataLoader._load_row_based_summary(df)
            if samples_row and len(samples_row) > 0:
                return samples_row
            # 兜底：如果是全曲线数据
            return DataLoader._load_column_based_curve(df)
        else:
            # 抗拉模式：优先尝试曲线读取
            if df.shape[0] >= 5:
                samples_curve = DataLoader._load_column_based_curve(df)
                if samples_curve and len(samples_curve) > 0:
                    return samples_curve
            return DataLoader._load_row_based_summary(df)

    @staticmethod
    def _is_invalid_name(name_str: str) -> bool:
        """检查是否为无效名字（单位或纯数字）"""
        if not name_str: return True
        s = str(name_str).strip().lower()
        try:
            float(s)
            return True
        except:
            pass

        invalid_keywords = [
            "%", "mpa", "gpa", "kn", "mm", "cm",
            "strain", "stress", "load", "extension", "displacement", "force",
            "time", "sec", "min", "machine", "specimen", "date", "no.", "id"
        ]
        if s in invalid_keywords: return True
        if any(f"({k})" in s for k in invalid_keywords): return True
        return False

    @staticmethod
    def _load_column_based_curve(df: pd.DataFrame) -> List[Dict]:
        """列式曲线读取"""
        samples = []
        cols = df.shape[1]
        for i in range(0, cols, 2):
            if i + 1 >= cols: break
            try:
                # 寻找数据起始行
                data_start_idx = -1
                for r in range(min(15, df.shape[0])):
                    try:
                        float(df.iloc[r, i])
                        float(df.iloc[r, i + 1])
                        data_start_idx = r
                        break
                    except:
                        continue

                if data_start_idx == -1: continue

                # 向上寻找名字
                sample_name = f"Specimen_{i // 2 + 1}"
                for r in range(data_start_idx - 1, -1, -1):
                    val = df.iloc[r, i]
                    if pd.isna(val) or str(val).strip() == "":
                        val = df.iloc[r, i + 1]
                    s_val = str(val).strip()
                    if not pd.isna(val) and s_val and not DataLoader._is_invalid_name(s_val):
                        sample_name = s_val
                        break

                sub_df = df.iloc[data_start_idx:, i:i + 2].apply(pd.to_numeric, errors='coerce').dropna()
                if not sub_df.empty and len(sub_df) > 3:
                    strain = sub_df.iloc[:, 0].values.astype(float)
                    stress = sub_df.iloc[:, 1].values.astype(float)
                    if np.max(np.abs(stress)) > 0.001:
                        samples.append({"name": sample_name, "strain": strain, "stress": stress, "type": "Curve"})
            except:
                continue
        return samples

    @staticmethod
    def _load_row_based_summary(df: pd.DataFrame) -> List[Dict]:
        """
        [Smart Fix] 解析行式数据
        适配格式：
        1. FSC-AIR  27.7  31.0
        2. 1  FSC-AIR  27.7  (忽略前面的序号 1)
        """
        samples = []
        current_name = "Sample_Unknown"

        for index, row in df.iterrows():
            row_values = row.values
            row_numbers = []
            found_name_in_this_row = False

            for cell in row_values:
                if pd.isna(cell) or str(cell).strip() == "": continue
                s_cell = str(cell).strip()

                try:
                    val = float(s_cell)
                    row_numbers.append(val)
                except ValueError:
                    # 遇到文本 -> 检查是否为名字
                    if not found_name_in_this_row and not DataLoader._is_invalid_name(s_cell):
                        # [Critical Logic] 如果在这一行中间发现了新名字
                        # 说明之前的数字可能是序号 (Index)，应丢弃
                        # 例如: "1" "FSC-AIR" "27.7" -> 遇到 FSC-AIR 时，清空之前的 [1.0]
                        if len(row_numbers) > 0:
                            # 只有当数字很少（比如只有一个序号）时才清空，防止误删
                            if len(row_numbers) < 3:
                                row_numbers = []

                        current_name = s_cell
                        found_name_in_this_row = True

            # 归档数据
            if row_numbers:
                # 过滤掉 0 值和极小值
                valid_stress = [v for v in row_numbers if v > 0.001]
                for v in valid_stress:
                    samples.append({
                        "name": current_name,
                        "strain": np.array([0.0]),  # 汇总模式无应变
                        "stress": np.array([float(v)]),  # 单个强度值
                        "type": "Summary"
                    })
        return samples