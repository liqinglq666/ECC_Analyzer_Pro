import sys
import numpy as np
import traceback
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QFileDialog, QHeaderView, QSplitter, QMessageBox,
                               QLabel, QComboBox, QTabWidget, QFrame, QProgressBar,
                               QApplication, QMenu, QCheckBox, QDoubleSpinBox,
                               QInputDialog, QButtonGroup, QAbstractItemView)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QColor, QFont, QBrush, QPixmap, QAction, QCursor
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from app.core.algorithms import TensileAnalyzer, CompressiveAnalyzer
from app.core.statistics import StatisticsCalculator
from app.data.loader import DataLoader
from app.data.exporter import DataExporter
from app.core.physics import MaterialConstants
from app.ui.dialogs import SettingsDialog
from app.ui.plotting import MplCanvas


# --- 1. 视图切换组件 ---
class ViewSwitcher(QFrame):
    viewChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(
            ".ViewSwitcher { background-color: #f0f2f5; border-radius: 18px; border: 1px solid #e0e0e0; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        self.btn_basic = self._create_btn("Basic Results")
        self.btn_adv = self._create_btn("Advanced Analysis")

        self.group.addButton(self.btn_basic, 0)
        self.group.addButton(self.btn_adv, 1)

        layout.addWidget(self.btn_basic)
        layout.addWidget(self.btn_adv)

        self.btn_basic.setChecked(True)
        self.group.buttonClicked.connect(self._on_click)

    def _create_btn(self, text):
        display_text = {
            "Basic Results": "基础结果",
            "Advanced Analysis": "高级分析",
        }.get(text, text)

        btn = QPushButton(display_text)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 15px;
                color: #5f6368;
                font-weight: 600;
                padding: 0 16px;
                background: transparent;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
            QPushButton:hover {
                color: #202124;
                background-color: rgba(0,0,0,0.05);
            }
            QPushButton:checked {
                background-color: white;
                color: #1a73e8;
                font-weight: 700;
                border: 1px solid #dadce0;
            }
        """)
        return btn

    def _on_click(self, btn):
        self.viewChanged.emit("Basic" if btn == self.btn_basic else "Advanced")


# --- 2. 拖拽上传组件 ---
class DragDropWidget(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(140)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.inner = QFrame()
        self.inner.setObjectName("DropZone")
        in_layout = QVBoxLayout(self.inner)
        in_layout.setAlignment(Qt.AlignCenter)

        self.lbl_icon = QLabel("📂")
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setStyleSheet("font-size: 48px; color: #9aa0a6; background: transparent;")

        self.lbl_main = QLabel("导入试验数据")
        self.lbl_main.setAlignment(Qt.AlignCenter)
        self.lbl_main.setStyleSheet("font-size: 16px; font-weight: bold; color: #3c4043; background: transparent;")

        self.lbl_sub = QLabel("拖拽 .xlsx / .csv 文件到这里\n或点击选择文件")
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        self.lbl_sub.setStyleSheet("font-size: 13px; color: #70757a; background: transparent;")

        in_layout.addWidget(self.lbl_icon)
        in_layout.addWidget(self.lbl_main)
        in_layout.addWidget(self.lbl_sub)

        layout.addWidget(self.inner)
        self.setStyleSheet("""
            #DropZone { border: 2px dashed #dadce0; border-radius: 12px; background-color: #f8f9fa; } 
            #DropZone:hover { border-color: #1a73e8; background-color: #e8f0fe; }
        """)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
            self.lbl_icon.setStyleSheet("font-size: 52px; color: #1a73e8; background: transparent;")
            self.inner.setStyleSheet("background-color: #e8f0fe; border: 2px dashed #1a73e8; border-radius: 12px;")
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.lbl_icon.setStyleSheet("font-size: 48px; color: #9aa0a6; background: transparent;")
        self.inner.setStyleSheet(
            "#DropZone { border: 2px dashed #dadce0; border-radius: 12px; background-color: #f8f9fa; }")

    def dropEvent(self, e):
        self.lbl_icon.setStyleSheet("font-size: 48px; color: #9aa0a6; background: transparent;")
        self.inner.setStyleSheet(
            "#DropZone { border: 2px dashed #dadce0; border-radius: 12px; background-color: #f8f9fa; }")
        files = [Path(u.toLocalFile()) for u in e.mimeData().urls()]
        if files:
            self.files_dropped.emit(files)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            try:
                self.window().load_files()
            except Exception:
                pass


# --- 3. 主窗口 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECC Analyzer Pro｜ECC/SHCC 力学数据分析")
        self.resize(1440, 920)
        self.setAcceptDrops(True)
        MaterialConstants.load_config()
        self.current_results = []
        self.group_stats_data = {}
        self.current_view_mode = "Basic"
        self.table_loading = False
        self._init_ui()
        self._apply_stylesheet()

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._setup_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(
            "QSplitter::handle { background-color: #e0e0e0; } QSplitter::handle:hover { background-color: #1a73e8; }")

        splitter.addWidget(self._setup_left_panel())
        splitter.addWidget(self._setup_right_panel())

        # [优化] 调整 Splitter 初始比例，给予左侧数据面板更多的初始宽度
        splitter.setSizes([700, 740])

        main_layout.addWidget(splitter)
        self._refresh_headers()

    def _setup_header(self):
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet("background-color: white; border-bottom: 1px solid #dadce0;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)
        h_layout.setSpacing(20)

        lbl_title = QLabel("ECC Analyzer")
        lbl_title.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #202124; font-family: 'Segoe UI', sans-serif;")
        h_layout.addWidget(lbl_title)

        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setFixedHeight(24)
        line.setStyleSheet("color: #dadce0;")
        h_layout.addWidget(line)

        h_layout.addWidget(QLabel("模式：", styleSheet="color: #5f6368; font-weight: 600; font-size: 13px;"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["抗拉 Tensile", "抗压 Compressive"])
        self.combo_mode.setFixedWidth(160)
        self.combo_mode.setCursor(Qt.PointingHandCursor)
        self.combo_mode.setStyleSheet("""
            QComboBox { padding: 5px 10px; border: 1px solid #dadce0; border-radius: 6px; background: white; font-weight: bold; color: #3c4043; }
            QComboBox::drop-down { border: 0px; }
            QComboBox:hover { border-color: #1a73e8; }
        """)
        self.combo_mode.currentIndexChanged.connect(self.on_mode_changed)
        h_layout.addWidget(self.combo_mode)

        h_layout.addStretch()

        self.view_switcher = ViewSwitcher()
        self.view_switcher.viewChanged.connect(self.on_view_changed_switcher)
        h_layout.addWidget(self.view_switcher)
        h_layout.addSpacing(20)

        def make_action_btn(text, icon="", primary=False, danger=False):
            btn = QPushButton(f"{icon} {text}" if icon else text)
            btn.setCursor(Qt.PointingHandCursor)
            if danger:
                base, bg, border, hover = "#d93025", "white", "1px solid #d93025", "#fce8e6"
            elif primary:
                base, bg, border, hover = "white", "#1a73e8", "none", "#1557b0"
            else:
                base, bg, border, hover = "#3c4043", "white", "1px solid #dadce0", "#f1f3f4"
            btn.setStyleSheet(f"""
                QPushButton {{ border: {border}; padding: 6px 16px; border-radius: 6px; font-weight: 600; color: {base}; background-color: {bg}; font-family: 'Segoe UI'; }}
                QPushButton:hover {{ background-color: {hover}; {'color: #d93025;' if danger else ''} }}
            """)
            return btn

        self.btn_export = make_action_btn("导出报告", "💾", primary=True)
        self.btn_export.clicked.connect(self.export_data)
        h_layout.addWidget(self.btn_export)

        self.btn_settings = make_action_btn("参数设置", "⚙️")
        self.btn_settings.clicked.connect(self.open_settings)
        h_layout.addWidget(self.btn_settings)

        self.btn_clear = make_action_btn("清空", "🗑️", danger=True)
        self.btn_clear.clicked.connect(self._clear_all_data)
        h_layout.addWidget(self.btn_clear)
        return header

    def _setup_left_panel(self):
        left_panel = QFrame()
        # [优化] 提升左侧最小宽度限制，防过度挤压
        left_panel.setMinimumWidth(640)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 12, 16)
        left_layout.setSpacing(16)
        left_panel.setStyleSheet("background-color: #f8f9fa;")

        self.drop_zone = DragDropWidget(self)
        self.drop_zone.files_dropped.connect(self.on_files_dropped)
        left_layout.addWidget(self.drop_zone)

        t_tools = QHBoxLayout()
        t_tools.setSpacing(8)

        def make_tool_btn(text, color_hover):
            btn = QPushButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.setStyleSheet(f"""
                QPushButton {{ border: none; background: transparent; color: #5f6368; font-weight: bold; padding: 0 8px; border-radius: 4px; }} 
                QPushButton:hover {{ background-color: {color_hover}; color: #202124; }}
            """)
            return btn

        self.btn_all = make_tool_btn("☑ 全选", "#d2e3fc")
        self.btn_all.clicked.connect(self.toggle_select_all)
        t_tools.addWidget(self.btn_all)
        t_tools.addStretch()

        btn_refresh = make_tool_btn("🔄 重新计算", "#feefc3")
        btn_refresh.clicked.connect(self.refresh_statistics_from_selection)
        t_tools.addWidget(btn_refresh)

        btn_copy = make_tool_btn("📋 复制表格", "#ceead6")
        btn_copy.clicked.connect(self.copy_table_to_clipboard)
        t_tools.addWidget(btn_copy)

        btn_delete = make_tool_btn("🗑️ 删除勾选", "#fad2cf")
        btn_delete.clicked.connect(self.delete_checked_items)
        t_tools.addWidget(btn_delete)
        left_layout.addLayout(t_tools)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QTableWidget.ContiguousSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)  # 表格行高稍微放宽，增强呼吸感
        self.table.itemChanged.connect(self.on_table_item_changed)
        self.table.cellClicked.connect(self.on_table_cell_clicked)

        self.table.setStyleSheet("""
            QTableWidget { 
                border: 1px solid #dadce0; background-color: white; border-radius: 8px; outline: none; font-family: 'Segoe UI', sans-serif;
            }
            QTableWidget::item { padding: 4px 8px; border-bottom: 1px solid #f1f3f4; color: #3c4043; }
            QTableWidget::item:selected { background-color: #e8f0fe; color: #1967d2; }
            QHeaderView::section { 
                background-color: #f8f9fa; border: none; border-bottom: 2px solid #dadce0; 
                padding: 6px; font-weight: 700; color: #444; font-size: 11px;
            }
            QTableWidget::indicator { width: 16px; height: 16px; border-radius: 3px; border: 2px solid #bdc1c6; margin-left: 10px; }
            QTableWidget::indicator:checked { background-color: #1a73e8; border: 2px solid #1a73e8; image: url(none); }
        """)
        left_layout.addWidget(self.table)

        status_bar = QHBoxLayout()
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setStyleSheet("color: #5f6368; font-size: 12px; font-weight: 500;")
        status_bar.addWidget(self.lbl_status)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar { border: none; background: #e0e0e0; border-radius: 3px; } QProgressBar::chunk { background: #1a73e8; border-radius: 3px; }")
        self.progress.hide()
        status_bar.addWidget(self.progress)
        left_layout.addLayout(status_bar)
        return left_panel

    def _setup_right_panel(self):
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 16, 16, 16)
        right_panel.setStyleSheet("background-color: white;")

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 0; } 
            QTabBar::tab { height: 36px; width: 140px; font-weight: 600; color: #5f6368; font-size: 13px; border-bottom: 3px solid transparent; margin-bottom: 8px; }
            QTabBar::tab:selected { color: #1a73e8; border-bottom: 3px solid #1a73e8; }
            QTabBar::tab:hover { color: #202124; background: #f8f9fa; }
        """)

        self.bar_canvas = MplCanvas(self)
        self.tabs.addTab(self.bar_canvas, "📊 统计图")

        c_widget = QWidget()
        c_layout = QVBoxLayout(c_widget)
        c_layout.setContentsMargins(0, 0, 0, 0)
        self.curve_canvas = MplCanvas(self)
        self.curve_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.curve_canvas.customContextMenuRequested.connect(self.show_chart_context_menu)
        self.toolbar = NavigationToolbar(self.curve_canvas, self)
        self.toolbar.setStyleSheet("background: white; border: none;")
        c_layout.addWidget(self.toolbar)
        c_layout.addWidget(self.curve_canvas)
        self.tabs.addTab(c_widget, "📈 曲线图")
        right_layout.addWidget(self.tabs)

        vis_ctrl = QFrame()
        vis_ctrl.setFixedHeight(60)
        vis_ctrl.setStyleSheet(
            "QFrame { background-color: #f8f9fa; border-top: 1px solid #dadce0; border-radius: 0 0 8px 8px; }")
        vc_layout = QHBoxLayout(vis_ctrl)
        vc_layout.setContentsMargins(20, 5, 20, 5)
        vc_layout.setSpacing(20)

        self.chk_params = QCheckBox("显示参数标注")
        self.chk_params.setChecked(True)
        self.chk_params.setCursor(Qt.PointingHandCursor)
        self.chk_params.setStyleSheet("QCheckBox { font-weight: 600; color: #3c4043; }")
        self.chk_params.toggled.connect(self.on_toggle_params)
        vc_layout.addWidget(self.chk_params)
        vc_layout.addStretch()

        lbl_col = QLabel("配色：")
        lbl_col.setStyleSheet("color: #5f6368; font-weight: bold;")
        vc_layout.addWidget(lbl_col)
        self.combo_color_main = QComboBox()
        self.combo_color_main.addItems(["科研蓝", "中性灰", "黑色", "红色", "绿色"])
        self.combo_color_main.setFixedWidth(100)
        self.combo_color_main.setCursor(Qt.PointingHandCursor)
        self.combo_color_main.currentIndexChanged.connect(self.on_visual_changed)
        vc_layout.addWidget(self.combo_color_main)

        self.btn_save_img = QPushButton("📷 保存图片")
        self.btn_save_img.setCursor(Qt.PointingHandCursor)
        self.btn_save_img.setFixedHeight(32)
        self.btn_save_img.setStyleSheet("""
            QPushButton { border: 1px solid #dadce0; border-radius: 16px; background: white; font-weight: bold; color: #3c4043; padding: 0 15px; } 
            QPushButton:hover { background-color: #f1f3f4; color: #202124; border-color: #bdc1c6; }
        """)
        self.btn_save_img.clicked.connect(self.save_chart_to_file)
        vc_layout.addWidget(self.btn_save_img)
        right_layout.addWidget(vis_ctrl)
        return right_panel

    # --- Interaction Handlers ---
    def on_table_cell_clicked(self, row, col):
        if col == 0: return
        item = self.table.item(row, 0)
        if item and (item.flags() & Qt.ItemIsUserCheckable):
            self.table.blockSignals(True)
            new_state = Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
            item.setCheckState(new_state)
            self.table.blockSignals(False)
            self.check_overlay_status()

    def toggle_select_all(self):
        rows = self.table.rowCount()
        if rows == 0: return
        any_unchecked = False
        for r in range(rows):
            item = self.table.item(r, 0)
            if (item.flags() & Qt.ItemIsUserCheckable) and item.checkState() == Qt.Unchecked:
                any_unchecked = True
                break
        target = Qt.Checked if any_unchecked else Qt.Unchecked
        self.table.blockSignals(True)
        for r in range(rows):
            item = self.table.item(r, 0)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(target)
        self.table.blockSignals(False)
        self.check_overlay_status()

    def check_overlay_status(self):
        selected = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.checkState() == Qt.Checked:
                data = item.data(Qt.UserRole)
                if isinstance(data, dict) and "Type" in data:
                    selected.append(data)

        if selected:
            self.tabs.setCurrentIndex(1)
            target_type = selected[0]["Type"]
            filtered = [d for d in selected if d.get("Type") == target_type]
            if len(filtered) > 1:
                self.curve_canvas.plot_multi_tensile(filtered)
                self.lbl_status.setText(f"已叠加 {len(filtered)} 个样品。")
            elif len(filtered) == 1:
                self.plot_curve_detail(filtered[0])
                self.lbl_status.setText(f"当前样品：{filtered[0]['Sample ID']}")
        else:
            self.curve_canvas.clear_plot()
            self.curve_canvas.draw()
            self.lbl_status.setText("未勾选样品。")

    def on_visual_changed(self):
        c_map = {0: "#2c3e50", 1: "#7f8c8d", 2: "#000000", 3: "#c0392b", 4: "#27ae60"}
        sel_col = c_map.get(self.combo_color_main.currentIndex(), "#2c3e50")
        MaterialConstants.update_config(STYLE_COLOR_RAW=sel_col)
        self.check_overlay_status()

    def open_settings(self):
        if SettingsDialog(self).exec():
            MaterialConstants.load_config()
            if self.current_results:
                self.recalculate_all_data()
            else:
                self.check_overlay_status()

    def copy_table_to_clipboard(self):
        selected = self.table.selectedRanges()
        if not selected:
            QMessageBox.information(self, "复制表格", "请先在表格中选中需要复制的单元格。")
            return
        selected.sort(key=lambda r: r.topRow())
        text = ""
        r = selected[0]
        for i in range(r.topRow(), r.bottomRow() + 1):
            row = []
            for j in range(r.leftColumn(), r.rightColumn() + 1):
                item = self.table.item(i, j)
                row.append(item.text() if item else "")
            text += "\t".join(row) + "\n"
        QApplication.clipboard().setText(text)
        self.lbl_status.setText("表格内容已复制到剪贴板。")

    def show_chart_context_menu(self, pos):
        menu = QMenu(self)
        act_copy = QAction("复制图片到剪贴板", self)
        act_copy.triggered.connect(self.copy_chart_to_clipboard)
        menu.addAction(act_copy)
        act_save = QAction("另存图片...", self)
        act_save.triggered.connect(self.save_chart_to_file)
        menu.addAction(act_save)
        menu.exec(self.curve_canvas.mapToGlobal(pos))

    def copy_chart_to_clipboard(self):
        pixmap = QPixmap(self.curve_canvas.size())
        self.curve_canvas.render(pixmap)
        QApplication.clipboard().setPixmap(pixmap)
        self.lbl_status.setText("图像已复制到剪贴板。")

    def on_view_changed_switcher(self, mode_str):
        self.current_view_mode = mode_str
        self.on_view_changed()

    def on_view_changed(self):
        self._refresh_headers()
        self._repopulate_table_and_charts()

    def on_mode_changed(self, index=0):
        self._clear_all_data()
        self.view_switcher.setVisible("Tensile" in self.combo_mode.currentText())
        self.tabs.setCurrentIndex(1 if "Tensile" in self.combo_mode.currentText() else 0)
        self._refresh_headers()

    def on_table_item_changed(self, item):
        if not self.table_loading and item.column() == 0:
            self.check_overlay_status()

    def on_toggle_params(self, checked):
        self.curve_canvas.set_text_visibility(checked)

    def _format_value(self, val, fmt):
        if val is None: return "-"
        try:
            v_float = float(val)
            if 0 < abs(v_float) < 0.01: return f"{v_float:.2e}"
            return f"{v_float:{fmt}}"
        except:
            return str(val)

    def save_chart_to_file(self):
        target_canvas = self.bar_canvas if self.tabs.currentIndex() == 0 else self.curve_canvas
        fname = f"Chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path, _ = QFileDialog.getSaveFileName(self, "保存图片", fname, "Images (*.png *.jpg *.pdf *.svg)")
        if path:
            try:
                target_canvas.fig.savefig(path, dpi=300, bbox_inches="tight")
                self.lbl_status.setText(f"图片已保存：{Path(path).name}")
                QMessageBox.information(self, "保存成功", "图片已成功保存。")
            except Exception as exc:
                QMessageBox.critical(self, "保存失败", str(exc))

    def export_data(self):
        if not self.current_results:
            QMessageBox.information(self, "导出报告", "当前还没有可导出的分析数据。")
            return

        is_tensile = "Tensile" in self.combo_mode.currentText() or "抗拉" in self.combo_mode.currentText()
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
            QMessageBox.warning(self, "导出报告", "请先勾选需要导出的样品。")
            return

        path, _ = QFileDialog.getSaveFileName(self, "导出 Excel 报告", default_name, "Excel (*.xlsx)")
        if not path:
            return

        self.lbl_status.setText("正在导出 Excel 报告...")
        QApplication.processEvents()

        ok = DataExporter.export_excel(items, Path(path))
        if ok:
            self.lbl_status.setText("导出完成。")
            QMessageBox.information(self, "导出成功", f"已导出 {len(items)} 个样品。")
        else:
            self.lbl_status.setText("导出失败。")
            QMessageBox.critical(
                self,
                "导出失败",
                "导出失败。请先关闭目标 Excel 文件，并确认目标文件夹可写。",
            )
    def delete_checked_items(self):
        is_tensile = "Tensile" in self.combo_mode.currentText()
        removed = 0
        self.table.blockSignals(True)

        if is_tensile:
            del_list = []
            keep_ids = set()
            for r in range(self.table.rowCount()):
                it = self.table.item(r, 0)
                d = it.data(Qt.UserRole)
                if it.checkState() == Qt.Checked and isinstance(d, dict):
                    del_list.append(d)
                elif isinstance(d, dict):
                    keep_ids.add(id(d))

            if not del_list:
                self.table.blockSignals(False)
                return

            if QMessageBox.question(self, "Delete Items", f"Are you sure you want to delete {len(del_list)} items?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
                self.table.blockSignals(False)
                return

            for d in del_list:
                if d in self.current_results:
                    self.current_results.remove(d)
                    removed += 1

            if removed: self._repopulate_table_and_charts(keep_ids)
        else:
            del_names = set()
            keep_ids = set()
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0).checkState() == Qt.Checked:
                    del_names.add(self.table.item(r, 1).text())
                else:
                    d = self.table.item(r, 0).data(Qt.UserRole)
                    if isinstance(d, dict): keep_ids.add(id(d))

            if not del_names:
                self.table.blockSignals(False)
                return

            if QMessageBox.question(self, "Delete Groups", f"Are you sure you want to delete {len(del_names)} groups?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
                self.table.blockSignals(False)
                return

            for res in list(self.current_results):
                if str(res.get("Sample ID", "")).strip() in del_names:
                    self.current_results.remove(res)
                    removed += 1

            if removed: self._repopulate_table_and_charts(keep_ids)

        self.table.blockSignals(False)
        self.refresh_statistics_from_selection()

    # --- File Loading Methods ---
    def load_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Load", "", "Data (*.xlsx *.xls *.csv)")
        if files: self.on_files_dropped([Path(f) for f in files])

    def on_files_dropped(self, files):
        limit, ok = QInputDialog.getInt(self, "Config", "Sheets per file:", 1, 1, 100)
        if ok:
            self._clear_all_data()
            self._refresh_headers()
            self.progress.show()
            QTimer.singleShot(100, lambda: self.process_files(files, limit))

    def process_files(self, files, limit):
        mode = "Tensile" if "Tensile" in self.combo_mode.currentText() else "Compressive"
        try:
            for f in files:
                if "~$" in f.name: continue
                samples, _ = DataLoader.load_file_smart(f, limit, mode)
                if not samples: continue
                for s in samples:
                    try:
                        res = {}
                        if len(s['stress']) >= 1:
                            if mode == "Tensile":
                                an = TensileAnalyzer(s['strain'], s['stress'])
                            else:
                                an = CompressiveAnalyzer(s['strain'], s['stress'])
                            res = an.run_analysis()
                            res["raw_strain"] = getattr(an, "raw_strain", s['strain'])
                            res["raw_stress"] = getattr(an, "raw_stress", s['stress'])

                        sheet_suffix = f" [{s.get('sheet_name')}]" if s.get('sheet_name') != "CSV" else ""
                        res.update({
                            "Sample ID": s['name'],
                            "Source File": f.name + sheet_suffix,
                            "Type": mode
                        })
                        self.current_results.append(res)
                    except Exception as e:
                        print(f"Error processing sample {s.get('name')}: {e}")
                        continue

            if self.current_results:
                self._repopulate_table_and_charts()
                self.refresh_statistics_from_selection()
                self.lbl_status.setText(f"Loaded {len(self.current_results)}")
            else:
                QMessageBox.warning(self, "No Data", "No valid data extracted.")

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Process Error: {str(e)}")
        finally:
            self.progress.hide()

    def plot_curve_detail(self, d):
        self.curve_canvas.axes.set_title(f"Sample: {d.get('Sample ID', 'Unknown')}", fontweight='bold')
        view_mode = "advanced" if "Advanced" in self.current_view_mode else "basic"
        self.curve_canvas.plot_tensile(d["raw_strain"], d["raw_stress"], d.get('Sample ID', 'Unknown'), d,
                                       True, False, self.chk_params.isChecked(), view_mode)

    # --- Statistics Methods ---
    def refresh_statistics_from_selection(self):
        if "Tensile" not in self.combo_mode.currentText() and "抗拉" not in self.combo_mode.currentText():
            return
        selected = {}
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.checkState() == Qt.Checked:
                data = item.data(Qt.UserRole)
                if isinstance(data, dict):
                    source = data["Source File"]
                    selected.setdefault(source, []).append(data)

        if not selected:
            QMessageBox.information(self, "统计", "请先勾选至少一个样品。")
            return

        self.group_stats_data = {f: StatisticsCalculator.get_group_stats(items) for f, items in selected.items()}
        self.plot_tensile_bars()

        view = self.current_view_mode
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.text() == "AVG":
                source = item.data(Qt.UserRole)
                if source in self.group_stats_data:
                    self._update_summary_row_values(r, self.group_stats_data[source], view, False)
                    self._update_summary_row_values(r + 1, self.group_stats_data[source], view, True)
                else:
                    self._clear_summary_row(r)
                    self._clear_summary_row(r + 1)
        self.check_overlay_status()

    def _create_item(self, text, is_header=False, align=Qt.AlignCenter):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(align)
        if is_header:
            item.setFlags(Qt.ItemIsEnabled)
            f = QFont()
            f.setBold(True)
            item.setFont(f)
        else:
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        return item

    def _basic_metric_spec(self):
        return [
            ("E_eff (GPa)", ".2f", "有效模量\nE_eff (GPa)"),
            ("First Crack Strength (MPa)", ".2f", "初裂强度\nσ_cr (MPa)"),
            ("Ultimate Stress (MPa)", ".2f", "峰值强度\nσ_u (MPa)"),
            ("Peak Strain (%)", ".2f", "峰值应变\nε_peak (%)"),
            ("Ultimate Strain (%)", ".2f", "极限应变\nε_u (%)"),
        ]

    def _advanced_metric_spec(self):
        return [
            ("E_init (GPa)", ".2f", "初始模量\nE_init (GPa)"),
            ("Fracture Energy (kJ/m²)", ".1f", "断裂能指标\nG_F (kJ/m²)"),
            ("Hardening Capacity (%)", ".2f", "硬化容量\nΔε_sh (%)"),
            ("Plateau Stability (CV)", ".2e", "平台波动\nCV_σ"),
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

    def _add_tensile_summary_row(self, f, stats):
        bg = QBrush(QColor("#f8f9fa"))
        bold_font = QFont()
        bold_font.setBold(True)
        r = self.table.rowCount()
        self.table.insertRow(r)
        it_avg = self._create_item("AVG", is_header=True, align=Qt.AlignLeft | Qt.AlignVCenter)
        it_avg.setData(Qt.UserRole, f)
        it_avg.setBackground(bg)
        it_avg.setFont(bold_font)
        self.table.setItem(r, 0, it_avg)

        it_grp = self._create_item(f, is_header=True, align=Qt.AlignLeft | Qt.AlignVCenter)
        it_grp.setBackground(bg)
        it_grp.setFont(bold_font)
        self.table.setItem(r, 1, it_grp)

        r2 = self.table.rowCount()
        self.table.insertRow(r2)
        it_sd = self._create_item("SD", is_header=True, align=Qt.AlignLeft | Qt.AlignVCenter)
        it_sd.setBackground(bg)
        self.table.setItem(r2, 0, it_sd)

        it_empty = self._create_item("", is_header=True)
        it_empty.setBackground(bg)
        self.table.setItem(r2, 1, it_empty)

        for row in [r, r2]:
            for c in range(2, self.table.columnCount()):
                it = self._create_item("-", is_header=True, align=Qt.AlignCenter)
                it.setBackground(bg)
                self.table.setItem(row, c, it)

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

    def _process_compressive_stats(self, keep_ids):
        grps = {}
        for r in self.current_results:
            grps.setdefault(str(r.get("Sample ID", "Unknown")).strip(), {'vals': [], 'first': r})['vals'].append(
                r.get("Peak Stress (MPa)", 0))
        self.group_stats_data = grps
        self.table.setRowCount(len(grps))
        r = 0
        for n, d in grps.items():
            vals = np.array(d['vals'])
            mean = np.mean(vals)
            std = np.std(vals, ddof=1) if len(vals) > 1 else 0

            it = self._create_item("", is_header=False, align=Qt.AlignLeft | Qt.AlignVCenter)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            it.setCheckState(Qt.Unchecked if keep_ids and id(d['first']) in keep_ids else Qt.Checked)
            it.setData(Qt.UserRole, d['first'])
            self.table.setItem(r, 0, it)

            self.table.setItem(r, 1, self._create_item(n, align=Qt.AlignLeft | Qt.AlignVCenter))
            self.table.setItem(r, 2, self._create_item(f"{mean:.2f}", align=Qt.AlignCenter))
            self.table.setItem(r, 3, self._create_item(f"± {std:.2f}", align=Qt.AlignCenter))
            self.table.setItem(r, 4, self._create_item(str(len(vals)), align=Qt.AlignCenter))
            r += 1
        self.plot_compressive_bars(list(grps.keys()))

    def plot_compressive_bars(self, names):
        self.bar_canvas.clear_plot()
        clean_names = [Path(n).stem for n in names]
        means = []
        stds = []
        for n in names:
            vals = self.group_stats_data[n]['vals']
            means.append(np.mean(vals))
            stds.append(np.std(vals, ddof=1) if len(vals) > 1 else 0)
        self.bar_canvas.plot_single_metric_bars(clean_names, means, stds, ylabel="Compressive Strength, σ (MPa)")

    def _clear_summary_row(self, r):
        for c in range(2, self.table.columnCount()):
            self.table.setItem(r, c, QTableWidgetItem("-"))

    def _refresh_headers(self):
        mode = self.combo_mode.currentText()
        base_headers = ["显示", "样品"]

        if "Tensile" in mode or "抗拉" in mode:
            metric_headers = [label for _, _, label in self._current_tensile_metric_spec()]
        else:
            metric_headers = ["平均强度\nσ_mean (MPa)", "标准差\nSD (MPa)", "数量\nN"]

        self.table.setColumnCount(len(base_headers) + len(metric_headers))
        self.table.setHorizontalHeaderLabels(base_headers + metric_headers)
        self.table.horizontalHeader().setMinimumHeight(48)
        self.table.setColumnWidth(0, 48)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(2, len(base_headers) + len(metric_headers)):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)

    def _repopulate_table_and_charts(self, preserved_ids=set()):
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table_loading = True
        self.table.setRowCount(0)

        if "Tensile" in self.combo_mode.currentText():
            self._process_tensile_stats(preserved_ids)
        else:
            self._process_compressive_stats(preserved_ids)

        self.table_loading = False
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)

    def _process_tensile_stats(self, keep_ids):
        grps = {}
        for r in self.current_results:
            grps.setdefault(r["Source File"], []).append(r)
        self.group_stats_data = grps
        for f, items in grps.items():
            for it in items:
                self._add_tensile_row(it, keep_ids)
            self._add_tensile_summary_row(f, {})

    def on_row_clicked(self, it):
        pass

    def _apply_stylesheet(self):
        self.setStyleSheet(
            "QMainWindow { background: #fcfcfc } QFrame { background: white } QComboBox { padding: 2px } QTabWidget::pane { border: 0 }")

    def recalculate_all_data(self):
        self.progress.show()
        self.lbl_status.setText("Recalculating...")
        QApplication.processEvents()
        count = 0
        for res in self.current_results:
            if "raw_strain" not in res: continue
            try:
                analyzer = TensileAnalyzer(res["raw_strain"], res["raw_stress"]) if res[
                                                                                        "Type"] == "Tensile" else CompressiveAnalyzer(
                    res["raw_strain"], res["raw_stress"])
                res.update(analyzer.run_analysis())
                count += 1
            except Exception:
                pass
        self._repopulate_table_and_charts()
        self.refresh_statistics_from_selection()
        self.progress.hide()
        self.lbl_status.setText(f"Updated {count} samples.")

    def _clear_all_data(self):
        self.table.setRowCount(0)
        self.current_results = []
        self.group_stats_data = {}
        self.current_viewing_data = None
        self.curve_canvas.clear_plot()
        self.curve_canvas.draw()
        self.bar_canvas.clear_plot()
        self.bar_canvas.draw()
        self.lbl_status.setText("Ready")