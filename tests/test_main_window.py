"""主窗口入口与模式切换回归测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import numpy as np

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from app.ui.main_window import MainWindow


def test_main_window_uses_single_implementation():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.combo_mode.currentText() == "抗拉 Tensile"
        assert window.view_switcher.btn_basic.text() == "基础结果"
        assert window.view_switcher.btn_adv.text() == "高级分析"
        assert window.table.columnCount() == 7
        assert len(window._current_tensile_metric_spec()) == 5

        window.view_switcher.btn_adv.click()
        assert window.current_view_mode == "Advanced"
        assert window.table.columnCount() == 6
        assert len(window._current_tensile_metric_spec()) == 4

        window.combo_mode.setCurrentIndex(1)
        assert window.combo_mode.currentText() == "抗压 Compressive"
        assert window.table.columnCount() == 5

        window.combo_mode.setCurrentIndex(0)
        assert window.table.columnCount() == 6
    finally:
        window.close()

def _sample(name, offset=0.0):
    return {
        "raw_strain": np.linspace(0.0, 0.03, 16) + offset,
        "raw_stress": np.linspace(0.0, 3.0, 16),
        "Type": "Tensile",
        "Sample ID": name,
        "Source File": "demo.xlsx",
        "E_eff (GPa)": 5.0,
        "First Crack Strength (MPa)": 1.5,
        "Ultimate Stress (MPa)": 3.0,
        "Peak Strain (%)": 3.0,
        "Ultimate Strain (%)": 3.0,
        "E_init (GPa)": 6.0,
        "Fracture Energy (kJ/m²)": 2.0,
        "Hardening Capacity (%)": 2.0,
        "Plateau Stability (CV)": 0.1,
    }


def test_view_switch_keeps_checks_and_recalculates_statistics():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.current_results = [_sample("A"), _sample("B", 0.001)]
        window._repopulate_table_and_charts()
        window.refresh_statistics_from_selection()
        window.table.item(1, 0).setCheckState(Qt.Unchecked)
        window.tabs.setCurrentIndex(0)

        window.view_switcher.btn_adv.click()
        assert window.table.item(1, 0).checkState() == Qt.Unchecked
        assert window.table.columnCount() == 6
        assert window.table.item(2, 2).text() == "6.00"
        assert window.tabs.currentIndex() == 0

        window.table.item(0, 0).setCheckState(Qt.Unchecked)
        window.refresh_statistics_from_selection()
        assert window.table.item(2, 2).text() == "-"
        assert window.group_stats_data == {}
    finally:
        window.close()


def test_delete_uses_sample_identity(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        first, second = _sample("A"), _sample("B", 0.001)
        window.current_results = [first, second]
        window._repopulate_table_and_charts()
        window.table.item(0, 0).setCheckState(Qt.Unchecked)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window.delete_checked_items()
        assert len(window.current_results) == 1
        assert window.current_results[0] is first
    finally:
        window.close()
