import pandas as pd
import numpy as np
import traceback
from pathlib import Path
from typing import List, Dict, Any


class DataExporter:
    """
    Excel exporter for ECC Analyzer Pro.

    The exporter now returns True/False instead of silently swallowing failures.
    A small MainWindow patch uses this return value to avoid showing a false
    success message when Excel is open or the target path is not writable.
    """

    SCIENTIFIC_HEADER_MAP = {
        # Tensile
        "E_eff (GPa)": "E_eff (GPa)",
        "First Crack Strength (MPa)": "σ_cr (MPa)",
        "Ultimate Stress (MPa)": "σ_u (MPa)",
        "Peak Strain (%)": "ε_peak (%)",
        "Ultimate Strain (%)": "ε_u (%)",
        "E_init (GPa)": "E_init (GPa)",
        "Strain Energy (kJ/m³)": "E_v (kJ/m³)",
        "Fracture Energy (kJ/m²)": "G_F (kJ/m²)",
        "Hardening Capacity (%)": "Δε_sh (%)",
        "Plateau Stability (CV)": "CV_σ",
        # Compressive
        "Mean Strength (MPa)": "σ_mean (MPa)",
        "Standard Deviation": "SD (MPa)",
        "Sample Count": "N",
    }

    @staticmethod
    def export_excel(checked_data: List[Dict[str, Any]], filepath: Path) -> bool:
        if not checked_data:
            return False

        is_tensile = not any(item.get("Type") == "Compressive" for item in checked_data)
        sorted_items = sorted(checked_data, key=lambda x: (str(x.get("Source File", "")), str(x.get("Sample ID", ""))))

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                if is_tensile:
                    df_raw = DataExporter._make_tensile_raw_df(sorted_items)
                    if not df_raw.empty:
                        df_raw.to_excel(writer, sheet_name="Raw Data (Curves)", index=False)

                    cols = [
                        "E_eff (GPa)",
                        "First Crack Strength (MPa)",
                        "Ultimate Stress (MPa)",
                        "Peak Strain (%)",
                        "Ultimate Strain (%)",
                        "E_init (GPa)",
                        "Strain Energy (kJ/m³)",
                        "Fracture Energy (kJ/m²)",
                        "Hardening Capacity (%)",
                        "Plateau Stability (CV)",
                    ]
                    df_summary = DataExporter._make_detailed_tensile_summary(sorted_items, cols)
                    df_summary.rename(columns=DataExporter.SCIENTIFIC_HEADER_MAP, inplace=True)
                    df_summary.to_excel(writer, sheet_name="Tensile Analysis", index=False)
                else:
                    df_compressive = DataExporter._make_compressive_summary(sorted_items)
                    df_compressive.rename(columns=DataExporter.SCIENTIFIC_HEADER_MAP, inplace=True)
                    df_compressive.to_excel(writer, sheet_name="Compressive Strength", index=False)
            return True
        except PermissionError:
            print("Export failed: permission denied. Please close the Excel file first.")
            return False
        except Exception:
            traceback.print_exc()
            return False

    @staticmethod
    def _make_tensile_raw_df(data_list: List[Dict]) -> pd.DataFrame:
        raw_dict = {}
        max_len = 0
        arrays = []

        for item in data_list:
            strain = item.get("raw_strain")
            stress = item.get("raw_stress")
            name = str(item.get("Sample ID", "Sample")).strip()

            if strain is not None and stress is not None and len(strain) > 0:
                strain = np.array(strain).flatten()
                stress = np.array(stress).flatten()
                strain_pct = strain * 100.0

                col_strain = f"{name} - ε (%)"
                col_stress = f"{name} - σ (MPa)"
                arrays.append((col_strain, strain_pct))
                arrays.append((col_stress, stress))
                max_len = max(max_len, len(strain_pct))

        for col_name, arr in arrays:
            if len(arr) < max_len:
                raw_dict[col_name] = np.pad(arr, (0, max_len - len(arr)), constant_values=np.nan)
            else:
                raw_dict[col_name] = arr

        return pd.DataFrame(raw_dict)

    @staticmethod
    def _make_detailed_tensile_summary(data_list: List[Dict], value_keys: List[str]) -> pd.DataFrame:
        final_rows = []
        groups = {}
        for item in data_list:
            fname = item.get("Source File", "Unknown Group")
            groups.setdefault(fname, []).append(item)

        for fname, items in groups.items():
            group_vals = {k: [] for k in value_keys}

            for item in items:
                row = {
                    "Group / File": fname,
                    "Sample ID": item.get("Sample ID", ""),
                }
                for k in value_keys:
                    val = item.get(k, None)
                    if val is not None and isinstance(val, (int, float, np.number)) and np.isfinite(val):
                        row[k] = float(val)
                        group_vals[k].append(float(val))
                    else:
                        row[k] = val
                final_rows.append(row)

            if len(items) > 1:
                avg_row = {"Group / File": fname, "Sample ID": "AVG (Mean)"}
                sd_row = {"Group / File": fname, "Sample ID": "SD (Stdev)"}
                cv_row = {"Group / File": fname, "Sample ID": "COV (%)"}

                for k in value_keys:
                    vals = np.array(group_vals[k], dtype=float)
                    vals = vals[np.isfinite(vals)]
                    if len(vals) > 0:
                        mean_val = float(np.mean(vals))
                        std_val = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
                        avg_row[k] = mean_val
                        sd_row[k] = std_val
                        cv_row[k] = (std_val / mean_val * 100.0) if abs(mean_val) > 1e-9 else 0.0

                final_rows.append(avg_row)
                final_rows.append(sd_row)
                final_rows.append(cv_row)

            final_rows.append({"Sample ID": ""})

        return pd.DataFrame(final_rows)

    @staticmethod
    def _make_compressive_summary(data_list: List[Dict]) -> pd.DataFrame:
        if not data_list:
            return pd.DataFrame()

        clean_data = []
        for item in data_list:
            group_name = str(item.get("Sample ID", "")).strip() or str(item.get("Source File", "Unknown")).strip()
            try:
                stress = abs(float(item.get("Peak Stress (MPa)", 0)))
                clean_data.append({"Group": group_name, "Stress": stress})
            except (ValueError, TypeError):
                continue

        df = pd.DataFrame(clean_data)
        if df.empty:
            return pd.DataFrame()

        stats = df.groupby("Group")["Stress"].agg(["count", "mean", "std"]).reset_index()
        stats["std"] = stats["std"].fillna(0.0)
        stats["COV (%)"] = (stats["std"] / stats["mean"] * 100.0).fillna(0.0)

        stats.rename(columns={
            "Group": "Sample Group",
            "mean": "Mean Strength (MPa)",
            "std": "Standard Deviation",
            "count": "Sample Count",
        }, inplace=True)

        stats = stats.round(2)
        return stats[["Sample Group", "Mean Strength (MPa)", "Standard Deviation", "COV (%)", "Sample Count"]]
