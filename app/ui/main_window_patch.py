from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QApplication
from PySide6.QtCore import Qt

from app.ui.main_window import MainWindow as _BaseMainWindow
from app.data.exporter import DataExporter


class MainWindow(_BaseMainWindow):
    """Thin compatibility patch over the original MainWindow.

    The original export flow always displayed a success message after calling
    DataExporter.export_excel(). DataExporter now returns True/False, and this
    override uses that status to avoid false success messages.
    """

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
