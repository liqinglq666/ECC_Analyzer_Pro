from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QFileDialog, QMessageBox, QApplication, QHeaderView
from PySide6.QtCore import Qt

from app.ui.main_window import MainWindow as _BaseMainWindow
from app.data.exporter import DataExporter


class MainWindow(_BaseMainWindow):
    """Compatibility patch over the original MainWindow.

    This subclass keeps the original UI layout but aligns the visible Basic table
    with the current mechanics model:
    - Peak Strain (epsilon_peak) is now displayed explicitly.
    - Ultimate Strain is displayed as Limit Strain (epsilon_u), not epsilon_tu.
    - Export status uses DataExporter's True/False return value.
    """

    def _basic_metric_spec(self):
        return [
            ("E_eff (GPa)", ".2f", "Modulus\nE_eff (GPa)"),
            ("First Crack Strength (MPa)", ".2f", "First Crack\nσ_cr (MPa)"),
            ("Ultimate Stress (MPa)", ".2f", "Peak Stress\nσ_u (MPa)"),
            ("Peak Strain (%)", ".2f", "Peak Strain\nε_peak (%)"),
            ("Ultimate Strain (%)", ".2f", "Limit Strain\nε_u (%)"),
        ]

    def _advanced_metric_spec(self):
        return [
            ("E_init (GPa)", ".2f", "Init Modulus\nE_init (GPa)"),
            ("Fracture Energy (kJ/m²)", ".1f", "Fracture Energy\nG_F (kJ/m²)"),
            ("Hardening Capacity (%)", ".2f", "Capacity\nΔε_sh (%)"),
            ("Plateau Stability (CV)", ".2e", "Stability\nCV_σ"),
        ]

    def _current_tensile_metric_spec(self):
        return self._basic_metric_spec() if "Basic" in self.current_view_mode else self._advanced_metric_spec()

    def _add_tensile_row(self, d, keep_ids):
        r = self.table.rowCount()
        self.table.insertRow(r)

        check_item = self._create_item("", is_header=False, align=Qt.AlignLeft | Qt.AlignVCenter)
        check_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
        check_item.setCheckState(Qt.Unchecked if keep_ids and id(d) in keep_ids else Qt.Checked)
        check_item.setData(Qt.UserRole, d)
        self.table.setItem(r, 0, check_item)
        self.table.setItem(r, 1, self._create_item(d.get("Sample ID", "Unknown"), align=Qt.AlignLeft | Qt.AlignVCenter))

        for i, (key, fmt, _) in enumerate(self._current_tensile_metric_spec()):
            value = d.get(key, 0)
            self.table.setItem(r, 2 + i, self._create_item(self._format_value(value, fmt), align=Qt.AlignCenter))

    def _update_summary_row_values(self, r, s, v, is_sd):
        spec = self._basic_metric_spec() if "Basic" in v else self._advanced_metric_spec()
        suffix = "_sd" if is_sd else "_mean"

        for i, (key, fmt, _) in enumerate(spec):
            value = s.get(key + suffix, 0)
            txt = self._format_value(value, fmt)
            disp = f"± {txt}" if is_sd else txt
            item = self._create_item(disp, is_header=True, align=Qt.AlignCenter)
            if not is_sd:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.table.setItem(r, 2 + i, item)

    def plot_tensile_bars(self):
        if not self.group_stats_data:
            self.bar_canvas.clear_plot()
            return

        spec = self._current_tensile_metric_spec()
        groups = list(self.group_stats_data.keys())
        clean_names = [Path(g).stem[:15] for g in groups]

        metrics_data = {}
        for group, clean_name in zip(groups, clean_names):
            stats = self.group_stats_data[group]
            metrics_data[clean_name] = {
                "means": [stats.get(key + "_mean", 0) for key, _, _ in spec],
                "stds": [stats.get(key + "_sd", 0) for key, _, _ in spec],
            }

        labels = [key for key, _, _ in spec]
        self.bar_canvas.plot_grouped_statistics(clean_names, metrics_data, labels)

    def _refresh_headers(self):
        mode = self.combo_mode.currentText()
        base_headers = ["Show", "Sample"]

        if "Tensile" in mode:
            metric_headers = [label for _, _, label in self._current_tensile_metric_spec()]
        else:
            metric_headers = ["Mean Strength\nσ_mean (MPa)", "Std Dev\nSD (MPa)", "Count\nN"]

        self.table.setColumnCount(len(base_headers) + len(metric_headers))
        self.table.setHorizontalHeaderLabels(base_headers + metric_headers)
        self.table.horizontalHeader().setMinimumHeight(46)
        self.table.setColumnWidth(0, 45)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(2, len(base_headers) + len(metric_headers)):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)

    def export_data(self):
        if not self.current_results:
            QMessageBox.information(self, "Export", "No data to export.")
            return

        is_tensile = "Tensile" in self.combo_mode.currentText()
        date_str = datetime.now().strftime("%Y%m%d")
        default_name = f"Tensile_Report_{date_str}.xlsx" if is_tensile else f"Compressive_Report_{date_str}.xlsx"

        items = []
        if is_tensile:
            for r in range(self.table.rowCount()):
                check_item = self.table.item(r, 0)
                if check_item and check_item.checkState() == Qt.Checked:
                    data = check_item.data(Qt.UserRole)
                    if isinstance(data, dict):
                        items.append(data)
        else:
            names = set()
            for r in range(self.table.rowCount()):
                check_item = self.table.item(r, 0)
                name_item = self.table.item(r, 1)
                if check_item and name_item and check_item.checkState() == Qt.Checked:
                    names.add(name_item.text())
            for res in self.current_results:
                if str(res.get("Sample ID", "")).strip() in names:
                    items.append(res)

        if not items:
            QMessageBox.warning(self, "Export", "No selected data to export.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export", default_name, "Excel (*.xlsx)")
        if not path:
            return

        self.lbl_status.setText("Exporting...")
        QApplication.processEvents()

        ok = DataExporter.export_excel(items, Path(path))
        if ok:
            self.lbl_status.setText("Export complete.")
            QMessageBox.information(self, "Success", f"Exported {len(items)} samples.")
        else:
            self.lbl_status.setText("Export failed.")
            QMessageBox.critical(
                self,
                "Export Failed",
                "Export failed. Please close the target Excel file and check that the folder is writable.",
            )
