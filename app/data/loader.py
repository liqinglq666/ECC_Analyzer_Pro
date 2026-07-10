from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class DataLoader:
    MIN_CURVE_POINTS = 5

    @staticmethod
    def load_file_smart(
        file_path: Path,
        max_sheets: int = 10,
        mode: str = "Tensile",
    ) -> Tuple[Optional[List[Dict]], Optional[str]]:
        file_path = Path(file_path)
        ext = file_path.suffix.lower()
        if ext not in {".xlsx", ".xls", ".csv"}:
            return None, f"Unsupported format: {ext}"

        if ext == ".csv":
            try:
                df = pd.read_csv(
                    file_path,
                    header=None,
                    sep=None,
                    engine="python",
                    on_bad_lines="error",
                )
                samples = DataLoader._parse_dataframe(df, mode)
            except Exception as exc:
                return None, f"CSV Parse Error: {exc}"

            if not samples:
                return None, "CSV 中没有识别到有效曲线。"
            for sample in samples:
                sample["sheet_name"] = "CSV"
            return samples, None

        try:
            xls = pd.ExcelFile(file_path)
        except Exception:
            try:
                xls = pd.ExcelFile(file_path, engine="xlrd")
            except Exception as exc:
                return None, f"Cannot open Excel file: {exc}"

        all_samples: List[Dict] = []
        errors: list[str] = []
        try:
            for sheet_name in xls.sheet_names[:max_sheets]:
                try:
                    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                except Exception as exc:
                    errors.append(f"{sheet_name}: read failed ({exc})")
                    continue

                if df.empty:
                    continue

                try:
                    samples = DataLoader._parse_dataframe(df, mode)
                except Exception as exc:
                    errors.append(f"{sheet_name}: parse failed ({exc})")
                    continue

                if not samples:
                    errors.append(f"{sheet_name}: no valid data")
                    continue

                for sample in samples:
                    sample["sheet_name"] = sheet_name
                all_samples.extend(samples)
        finally:
            xls.close()

        if errors:
            detail = "; ".join(errors[:8])
            if len(errors) > 8:
                detail += f"; 另有 {len(errors) - 8} 个错误"
            return None, f"部分工作表解析失败，已中止导入：{detail}"
        if not all_samples:
            return None, "No valid data found."
        return all_samples, None

    @staticmethod
    def _parse_dataframe(df: pd.DataFrame, mode: str) -> List[Dict]:
        df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)
        if df.empty:
            return []

        if "Compressive" in mode:
            if df.shape[0] >= DataLoader.MIN_CURVE_POINTS:
                curves = DataLoader._load_column_based_curve(df)
                if curves:
                    return curves
            return DataLoader._load_row_based_summary(df)

        if df.shape[0] < DataLoader.MIN_CURVE_POINTS:
            return []
        return DataLoader._load_column_based_curve(df)

    @staticmethod
    def _is_invalid_name(name_str: str) -> bool:
        if not name_str:
            return True

        value = str(name_str).strip().lower()
        try:
            float(value)
            return True
        except ValueError:
            pass

        invalid_keywords = [
            "%", "mpa", "gpa", "kn", "mm", "cm",
            "strain", "stress", "load", "extension", "displacement", "force",
            "time", "sec", "min", "machine", "specimen", "date", "no.", "id",
            "应变", "應變", "应力", "應力", "载荷", "載荷", "位移",
        ]
        if value in invalid_keywords:
            return True
        return any(f"({keyword})" in value for keyword in invalid_keywords)

    @staticmethod
    def _find_data_start(df: pd.DataFrame, col_a: int, col_b: int) -> int | None:
        for row in range(min(15, df.shape[0])):
            try:
                float(df.iloc[row, col_a])
                float(df.iloc[row, col_b])
                return row
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _sample_name(df: pd.DataFrame, data_start: int, col_a: int, col_b: int, fallback: str) -> str:
        for row in range(data_start - 1, -1, -1):
            value = df.iloc[row, col_a]
            if pd.isna(value) or not str(value).strip():
                value = df.iloc[row, col_b]
            if pd.isna(value):
                continue
            text = str(value).strip()
            if text and not DataLoader._is_invalid_name(text):
                return text
        return fallback

    @staticmethod
    def _load_column_based_curve(df: pd.DataFrame) -> List[Dict]:
        samples: List[Dict] = []
        for col in range(0, df.shape[1], 2):
            if col + 1 >= df.shape[1]:
                break

            data_start = DataLoader._find_data_start(df, col, col + 1)
            if data_start is None:
                continue

            sub_df = (
                df.iloc[data_start:, col:col + 2]
                .apply(pd.to_numeric, errors="coerce")
                .dropna()
            )
            if len(sub_df) < DataLoader.MIN_CURVE_POINTS:
                continue

            strain = sub_df.iloc[:, 0].to_numpy(dtype=float)
            stress = sub_df.iloc[:, 1].to_numpy(dtype=float)
            if len(np.unique(strain)) < DataLoader.MIN_CURVE_POINTS:
                continue
            if np.ptp(stress) <= 1e-9 or np.max(np.abs(stress)) <= 0.001:
                continue

            name = DataLoader._sample_name(
                df,
                data_start,
                col,
                col + 1,
                f"Specimen_{col // 2 + 1}",
            )
            samples.append({"name": name, "strain": strain, "stress": stress, "type": "Curve"})
        return samples

    @staticmethod
    def _load_row_based_summary(df: pd.DataFrame) -> List[Dict]:
        samples: List[Dict] = []
        current_name = "Sample_Unknown"
        header_row, value_columns = DataLoader._detect_summary_value_columns(df)

        for row_pos, (_, row) in enumerate(df.iterrows()):
            if header_row is not None and row_pos <= header_row:
                continue

            row_numbers = []
            found_name = False
            for col_idx, cell in enumerate(row.values):
                if pd.isna(cell) or not str(cell).strip():
                    continue
                text = str(cell).strip()

                if value_columns is not None and col_idx not in value_columns:
                    if not found_name and not DataLoader._is_invalid_name(text):
                        current_name = text
                        found_name = True
                    continue

                try:
                    scale = value_columns[col_idx] if value_columns is not None else 1.0
                    row_numbers.append(float(text) * scale)
                except ValueError:
                    if not found_name and not DataLoader._is_invalid_name(text):
                        if 0 < len(row_numbers) < 3:
                            row_numbers = []
                        current_name = text
                        found_name = True

            if not row_numbers or (not found_name and len(row_numbers) > 3):
                continue

            for value in row_numbers:
                if abs(value) <= 0.001:
                    continue
                samples.append(
                    {
                        "name": current_name,
                        "strain": np.array([0.0]),
                        "stress": np.array([abs(float(value))]),
                        "type": "Summary",
                    }
                )
        return samples

    @staticmethod
    def _detect_summary_value_columns(
        df: pd.DataFrame,
    ) -> Tuple[Optional[int], Optional[Dict[int, float]]]:
        for row_pos in range(min(3, df.shape[0])):
            value_columns: Dict[int, float] = {}
            for col_idx, cell in enumerate(df.iloc[row_pos].values):
                if pd.isna(cell):
                    continue
                label = str(cell).strip().lower()
                if not label:
                    continue

                is_stress = any(token in label for token in ("stress", "应力", "應力", "strength", "强度"))
                is_excluded = any(
                    token in label
                    for token in ("load", "载荷", "載荷", "length", "width", "长度", "長度", "宽度", "寬度")
                )
                if is_stress and not is_excluded:
                    value_columns[col_idx] = 1e-7 if "dyn/cm" in label else 1.0

            if value_columns:
                return row_pos, value_columns
        return None, None
