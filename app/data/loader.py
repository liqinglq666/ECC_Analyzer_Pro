import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class DataLoader:
    """
    Smart data loader for ECC Analyzer Pro.

    Supported layouts
    -----------------
    1. Column-pair curves: strain/stress, strain/stress, ...
    2. Compressive row summaries: group name + one or more strength values.

    Compressive summary values are stored as positive magnitudes so files exported
    by machines with negative compressive stress convention remain usable.
    """

    MIN_CURVE_POINTS = 5

    @staticmethod
    def load_file_smart(file_path: Path, max_sheets: int = 10, mode: str = "Tensile") -> Tuple[Optional[List[Dict]], Optional[str]]:
        all_samples = []
        try:
            ext = file_path.suffix.lower()
            if ext not in [".xlsx", ".xls", ".csv"]:
                return None, f"Unsupported format: {ext}"

            if ext == ".csv":
                try:
                    df = pd.read_csv(file_path, header=None, sep=None, engine="python", on_bad_lines="skip")
                    samples = DataLoader._parse_dataframe(df, mode)
                    for s in samples:
                        s["sheet_name"] = "CSV"
                    all_samples.extend(samples)
                except Exception as e:
                    return None, f"CSV Parse Error: {e}"
            else:
                try:
                    xls = pd.ExcelFile(file_path)
                except Exception:
                    try:
                        xls = pd.ExcelFile(file_path, engine="xlrd")
                    except Exception:
                        return None, "Cannot open Excel file."

                for sheet_name in xls.sheet_names[:max_sheets]:
                    try:
                        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                        if df.empty:
                            continue
                        samples = DataLoader._parse_dataframe(df, mode)
                        for s in samples:
                            s["sheet_name"] = sheet_name
                        all_samples.extend(samples)
                    except Exception:
                        continue
                xls.close()

            if all_samples:
                return all_samples, None
            return None, "No valid data found."
        except Exception as e:
            return None, f"Load Error: {str(e)}"

    @staticmethod
    def _parse_dataframe(df: pd.DataFrame, mode: str) -> List[Dict]:
        df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)
        if df.empty:
            return []

        if "Compressive" in mode:
            # Try true curve parsing first. A summary table whose first two columns are
            # name/value will usually fail this check and fall back to row parsing.
            if df.shape[0] >= DataLoader.MIN_CURVE_POINTS:
                samples_curve = DataLoader._load_column_based_curve(df)
                if samples_curve:
                    return samples_curve
            return DataLoader._load_row_based_summary(df)

        if df.shape[0] >= DataLoader.MIN_CURVE_POINTS:
            samples_curve = DataLoader._load_column_based_curve(df)
            if samples_curve:
                return samples_curve
        return []

    @staticmethod
    def _is_invalid_name(name_str: str) -> bool:
        if not name_str:
            return True
        s = str(name_str).strip().lower()
        try:
            float(s)
            return True
        except Exception:
            pass

        invalid_keywords = [
            "%", "mpa", "gpa", "kn", "mm", "cm",
            "strain", "stress", "load", "extension", "displacement", "force",
            "time", "sec", "min", "machine", "specimen", "date", "no.", "id",
            "应变", "應變", "应力", "應力", "载荷", "載荷", "位移",
        ]
        if s in invalid_keywords:
            return True
        if any(f"({k})" in s for k in invalid_keywords):
            return True
        return False

    @staticmethod
    def _load_column_based_curve(df: pd.DataFrame) -> List[Dict]:
        samples = []
        cols = df.shape[1]
        for i in range(0, cols, 2):
            if i + 1 >= cols:
                break
            try:
                data_start_idx = -1
                for r in range(min(15, df.shape[0])):
                    try:
                        float(df.iloc[r, i])
                        float(df.iloc[r, i + 1])
                        data_start_idx = r
                        break
                    except Exception:
                        continue

                if data_start_idx == -1:
                    continue

                sample_name = f"Specimen_{i // 2 + 1}"
                for r in range(data_start_idx - 1, -1, -1):
                    val = df.iloc[r, i]
                    if pd.isna(val) or str(val).strip() == "":
                        val = df.iloc[r, i + 1]
                    s_val = str(val).strip()
                    if not pd.isna(val) and s_val and not DataLoader._is_invalid_name(s_val):
                        sample_name = s_val
                        break

                sub_df = df.iloc[data_start_idx:, i:i + 2].apply(pd.to_numeric, errors="coerce").dropna()
                if sub_df.empty or len(sub_df) < DataLoader.MIN_CURVE_POINTS:
                    continue

                strain = sub_df.iloc[:, 0].values.astype(float)
                stress = sub_df.iloc[:, 1].values.astype(float)
                unique_strain_count = len(np.unique(strain))
                stress_span = np.nanmax(stress) - np.nanmin(stress)

                if (
                    unique_strain_count >= DataLoader.MIN_CURVE_POINTS
                    and stress_span > 1e-9
                    and np.max(np.abs(stress)) > 0.001
                ):
                    samples.append({"name": sample_name, "strain": strain, "stress": stress, "type": "Curve"})
            except Exception:
                continue
        return samples

    @staticmethod
    def _load_row_based_summary(df: pd.DataFrame) -> List[Dict]:
        """
        Parse compressive summary rows.

        Examples:
        - FSC-AIR  27.7  31.0
        - 1  FSC-AIR  27.7
        - Group, Stress-1, Stress-2, Stress-3
        """
        samples = []
        current_name = "Sample_Unknown"
        header_row, value_columns = DataLoader._detect_summary_value_columns(df)

        for row_pos, (_, row) in enumerate(df.iterrows()):
            if header_row is not None and row_pos <= header_row:
                continue

            row_values = row.values
            row_numbers = []
            found_name_in_this_row = False

            for col_idx, cell in enumerate(row_values):
                if pd.isna(cell) or str(cell).strip() == "":
                    continue
                s_cell = str(cell).strip()

                if value_columns is not None and col_idx not in value_columns:
                    if not found_name_in_this_row and not DataLoader._is_invalid_name(s_cell):
                        current_name = s_cell
                        found_name_in_this_row = True
                    continue

                try:
                    scale = value_columns[col_idx] if value_columns is not None else 1.0
                    val = float(s_cell) * scale
                    row_numbers.append(val)
                except ValueError:
                    if not found_name_in_this_row and not DataLoader._is_invalid_name(s_cell):
                        # If a sample name appears after a small numeric prefix, that
                        # prefix is likely an index column rather than strength.
                        if 0 < len(row_numbers) < 3:
                            row_numbers = []
                        current_name = s_cell
                        found_name_in_this_row = True

            if row_numbers:
                # A long all-numeric row without a sample name is more likely a curve
                # row than a summary row, so do not explode it into many fake samples.
                if not found_name_in_this_row and len(row_numbers) > 3:
                    continue

                valid_stress = [abs(float(v)) for v in row_numbers if abs(float(v)) > 0.001]
                for v in valid_stress:
                    samples.append({
                        "name": current_name,
                        "strain": np.array([0.0]),
                        "stress": np.array([v]),
                        "type": "Summary",
                    })
        return samples

    @staticmethod
    def _detect_summary_value_columns(df: pd.DataFrame) -> Tuple[Optional[int], Optional[Dict[int, float]]]:
        """Detect stress columns in a header row and optional unit scales."""
        for row_pos in range(min(3, df.shape[0])):
            value_columns = {}
            row = df.iloc[row_pos]
            for col_idx, cell in enumerate(row.values):
                if pd.isna(cell):
                    continue
                label = str(cell).strip().lower()
                if not label:
                    continue

                is_stress = "stress" in label or "应力" in label or "應力" in label or "strength" in label or "强度" in label
                is_excluded = any(token in label for token in [
                    "load", "载荷", "載荷", "length", "width", "长度", "長度", "宽度", "寬度",
                ])
                if is_stress and not is_excluded:
                    scale = 1.0
                    if "dyn/cm" in label:
                        scale = 1e-7
                    value_columns[col_idx] = scale

            if value_columns:
                return row_pos, value_columns
        return None, None
