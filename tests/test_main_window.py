"""主窗口入口与模式切换回归测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

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
