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
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton { border: none; border-radius: 15px; color: #5f6368; font-weight: 600; padding: 0 15px; background: transparent; font-family: 'Segoe UI', sans-serif; }
            QPushButton:hover { color: #202124; background-color: rgba(0,0,0,0.05); }
            QPushButton:checked { background-color: white; color: #1a73e8; font-weight: bold; border: 1px solid #dadce0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
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

        self.lbl_main = QLabel("Import Data Files")
        self.lbl_main.setAlignment(Qt.AlignCenter)
        self.lbl_main.setStyleSheet("font-size: 16px; font-weight: bold; color: #3c4043; background: transparent;")

        self.lbl_sub = QLabel("Drag & Drop .xlsx / .csv here\nor click to browse")
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
        if files: self.files_dropped.emit(files)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            try:
                self.window().load_files()
            except:
                pass


# --- 3. 主窗口 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECC Analyzer Pro")
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
        splitter.setSizes([480, 960])

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

        h_layout.addWidget(QLabel("Mode:", styleSheet="color: #5f6368; font-weight: 600; font-size: 13px;"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Tensile (抗拉)", "Compressive (抗压)"])
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

        self.btn_export = make_action_btn("Export", "💾", primary=True)
        self.btn_export.clicked.connect(self.export_data)
        h_layout.addWidget(self.btn_export)

        self.btn_settings = make_action_btn("Settings", "⚙️")
        self.btn_settings.clicked.connect(self.open_settings)
        h_layout.addWidget(self.btn_settings)

        self.btn_clear = make_action_btn("Clear", "🗑️", danger=True)
        self.btn_clear.clicked.connect(self._clear_all_data)
        h_layout.addWidget(self.btn_clear)
        return header

    def _setup_left_panel(self):
        left_panel = QFrame()
        left_panel.setMinimumWidth(400)
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

        self.btn_all = make_tool_btn("☑ All", "#d2e3fc")
        self.btn_all.clicked.connect(self.toggle_select_all)
        t_tools.addWidget(self.btn_all)
        t_tools.addStretch()

        btn_refresh = make_tool_btn("🔄 Calc", "#feefc3")
        btn_refresh.clicked.connect(self.refresh_statistics_from_selection)
        t_tools.addWidget(btn_refresh)

        btn_copy = make_tool_btn("📋 Copy", "#ceead6")
        btn_copy.clicked.connect(self.copy_table_to_clipboard)
        t_tools.addWidget(btn_copy)

        btn_delete = make_tool_btn("🗑️ Del", "#fad2cf")
        btn_delete.clicked.connect(self.delete_checked_items)
        t_tools.addWidget(btn_delete)
        left_layout.addLayout(t_tools)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QTableWidget.ContiguousSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
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
                padding: 8px; font-weight: 700; color: #444; font-size: 11px;
            }
            QTableWidget::indicator { width: 16px; height: 16px; border-radius: 3px; border: 2px solid #bdc1c6; }
            QTableWidget::indicator:checked { background-color: #1a73e8; border: 2px solid #1a73e8; image: url(none); }
        """)
        left_layout.addWidget(self.table)

        status_bar = QHBoxLayout()
        self.lbl_status = QLabel("Ready")
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
        self.tabs.addTab(self.bar_canvas, "📊 Statistics")

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
        self.tabs.addTab(c_widget, "📈 Curves")
        right_layout.addWidget(self.tabs)

        vis_ctrl = QFrame()
        vis_ctrl.setFixedHeight(60)
        vis_ctrl.setStyleSheet(
            "QFrame { background-color: #f8f9fa; border-top: 1px solid #dadce0; border-radius: 0 0 8px 8px; }")
        vc_layout = QHBoxLayout(vis_ctrl)
        vc_layout.setContentsMargins(20, 5, 20, 5)
        vc_layout.setSpacing(20)

        self.chk_params = QCheckBox("Show Annotations")
        self.chk_params.setChecked(True)
        self.chk_params.setCursor(Qt.PointingHandCursor)
        self.chk_params.setStyleSheet("QCheckBox { font-weight: 600; color: #3c4043; }")
        self.chk_params.toggled.connect(self.on_toggle_params)
        vc_layout.addWidget(self.chk_params)
        vc_layout.addStretch()

        lbl_col = QLabel("Theme:")
        lbl_col.setStyleSheet("color: #5f6368; font-weight: bold;")
        vc_layout.addWidget(lbl_col)
        self.combo_color_main = QComboBox()
        self.combo_color_main.addItems(["Blue", "Gray", "Black", "Red", "Green"])
        self.combo_color_main.setFixedWidth(100)
        self.combo_color_main.setCursor(Qt.PointingHandCursor)
        self.combo_color_main.currentIndexChanged.connect(self.on_visual_changed)
        vc_layout.addWidget(self.combo_color_main)

        self.btn_save_img = QPushButton("📷 Save Image")
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
        sel = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item.checkState() == Qt.Checked:
                data = item.data(Qt.UserRole)
                if isinstance(data, dict) and "Type" in data:
                    sel.append(data)

        if sel:
            self.tabs.setCurrentIndex(1)
            target_type = sel[0]["Type"]
            filt = [d for d in sel if d.get("Type") == target_type]
            if len(filt) > 1:
                self.curve_canvas.plot_multi_tensile(filt)
                self.lbl_status.setText(f"Overlay: {len(filt)} samples.")
            elif len(filt) == 1:
                self.plot_curve_detail(filt[0])
                self.lbl_status.setText(f"Detail: {filt[0]['Sample ID']}")
        else:
            self.curve_canvas.clear_plot()
            self.curve_canvas.draw()
            self.lbl_status.setText("No selection.")

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
            QMessageBox.information(self, "Copy", "Select cells first.")
            return
        selected.sort(key=lambda r: r.topRow())
        text = ""
        r = selected[0]
        for i in range(r.topRow(), r.bottomRow() + 1):
            row = []
            for j in range(r.leftColumn(), r.rightColumn() + 1):
                it = self.table.item(i, j)
                row.append(it.text() if it else "")
            text += "\t".join(row) + "\n"
        QApplication.clipboard().setText(text)
        self.lbl_status.setText("Table Copied!")

    def show_chart_context_menu(self, pos):
        menu = QMenu(self)
        act_copy = QAction("Copy Image to Clipboard", self)
        act_copy.triggered.connect(self.copy_chart_to_clipboard)
        menu.addAction(act_copy)
        act_save = QAction("Save Image As...", self)
        act_save.triggered.connect(self.save_chart_to_file)
        menu.addAction(act_save)
        menu.exec(self.curve_canvas.mapToGlobal(pos))

    def copy_chart_to_clipboard(self):
        pixmap = QPixmap(self.curve_canvas.size())
        self.curve_canvas.render(pixmap)
        QApplication.clipboard().setPixmap(pixmap)
        self.lbl_status.setText("Image copied.")

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
        if not self.table_loading and item.column() == 0: self.check_overlay_status()

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
        path, _ = QFileDialog.getSaveFileName(self, "Save Image", fname, "Images (*.png *.jpg *.pdf *.svg)")
        if path:
            try:
                target_canvas.fig.savefig(path, dpi=300, bbox_inches='tight')
                self.lbl_status.setText(f"Saved: {Path(path).name}")
                QMessageBox.information(self, "Success", "Saved.")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def export_data(self):
        if not self.current_results: return
        is_tensile = "Tensile" in self.combo_mode.currentText()
        date_str = datetime.now().strftime("%Y%m%d")
        default_name = f"Tensile_Report_{date_str}.xlsx" if is_tensile else f"Compressive_Report_{date_str}.xlsx"

        items = []
        if is_tensile:
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0).checkState() == Qt.Checked:
                    d = self.table.item(r, 0).data(Qt.UserRole)
                    if isinstance(d, dict): items.append(d)
        else:
            names = set()
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0).checkState() == Qt.Checked:
                    names.add(self.table.item(r, 1).text())
            for res in self.current_results:
                if str(res.get("Sample ID", "")).strip() in names: items.append(res)

        if not items:
            QMessageBox.warning(self, "Export", "No selection.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export", default_name, "Excel (*.xlsx)")
        if path:
            self.lbl_status.setText("Exporting...")
            QApplication.processEvents()
            DataExporter.export_excel(items, Path(path))
            self.lbl_status.setText("Done.")
            QMessageBox.information(self, "Success", f"Exported {len(items)} samples.")

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
        if "Tensile" not in self.combo_mode.currentText(): return
        sel = {}
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).checkState() == Qt.Checked:
                d = self.table.item(r, 0).data(Qt.UserRole)
                if isinstance(d, dict):
                    f = d["Source File"]
                    if f not in sel: sel[f] = []
                    sel[f].append(d)

        if not sel:
            QMessageBox.information(self, "Info", "Select items.")
            return

        self.group_stats_data = {f: StatisticsCalculator.get_group_stats(items) for f, items in sel.items()}
        self.plot_tensile_bars()

        v = self.current_view_mode
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).text() == "AVG":
                f = self.table.item(r, 0).data(Qt.UserRole)
                if f in self.group_stats_data:
                    self._update_summary_row_values(r, self.group_stats_data[f], v, False)
                    self._update_summary_row_values(r + 1, self.group_stats_data[f], v, True)
                else:
                    self._clear_summary_row(r)
                    self._clear_summary_row(r + 1)
        self.check_overlay_status()

    # --- Table Data Helpers ---
    def _create_item(self, text, is_header=False, align=Qt.AlignCenter):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(align)
        if is_header:
            item.setFlags(Qt.ItemIsEnabled)
            f = QFont();
            f.setBold(True);
            item.setFont(f)
        else:
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        return item

    def _add_tensile_row(self, d, keep_ids):
        r = self.table.rowCount()
        self.table.insertRow(r)

        it = self._create_item("", is_header=False, align=Qt.AlignLeft | Qt.AlignVCenter)
        it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
        it.setCheckState(Qt.Unchecked if keep_ids and id(d) in keep_ids else Qt.Checked)
        it.setData(Qt.UserRole, d)
        self.table.setItem(r, 0, it)

        self.table.setItem(r, 1, self._create_item(d.get("Sample ID", "Unknown"), align=Qt.AlignLeft | Qt.AlignVCenter))

        v = self.current_view_mode
        if "Basic" in v:
            vals = [d.get('E_eff (GPa)', 0), d.get('First Crack Strength (MPa)', 0),
                    d.get('Ultimate Stress (MPa)', 0), d.get('Ultimate Strain (%)', 0)]
        else:
            vals = [d.get('E_init (GPa)', 0), d.get('Strain Energy (kJ/m³)', 0),
                    d.get('Fracture Energy (kJ/m²)', 0), d.get('Hardening Capacity (%)', 0),
                    d.get('Plateau Stability (CV)', 0)]

        fmts = [".2f", ".2f", ".2f", ".2f"] if "Basic" in v else [".2f", ".1f", ".1f", ".2f", ".2e"]
        for i, val in enumerate(vals):
            txt = self._format_value(val, fmts[i])
            self.table.setItem(r, 2 + i, self._create_item(txt, align=Qt.AlignCenter))

    def _add_tensile_summary_row(self, f, stats):
        bg = QBrush(QColor("#f8f9fa"))
        bold_font = QFont();
        bold_font.setBold(True)
        r = self.table.rowCount();
        self.table.insertRow(r)
        it_avg = self._create_item("AVG", is_header=True, align=Qt.AlignLeft | Qt.AlignVCenter)
        it_avg.setData(Qt.UserRole, f);
        it_avg.setBackground(bg);
        it_avg.setFont(bold_font)
        self.table.setItem(r, 0, it_avg)

        it_grp = self._create_item(f, is_header=True, align=Qt.AlignLeft | Qt.AlignVCenter)
        it_grp.setBackground(bg);
        it_grp.setFont(bold_font)
        self.table.setItem(r, 1, it_grp)

        r2 = self.table.rowCount();
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
        if "Basic" in v:
            keys = ["E_eff (GPa)", "First Crack Strength (MPa)", "Ultimate Stress (MPa)", "Ultimate Strain (%)"]
        else:
            keys = ["E_init (GPa)", "Strain Energy (kJ/m³)", "Fracture Energy (kJ/m²)", "Hardening Capacity (%)",
                    "Plateau Stability (CV)"]
        fmts = [".2f", ".2f", ".2f", ".2f"] if "Basic" in v else [".2f", ".1f", ".1f", ".2f", ".2e"]
        suff = "_sd" if is_sd else "_mean"
        for i, k in enumerate(keys):
            val = s.get(k + suff, 0);
            txt = self._format_value(val, fmts[i])
            disp = f"± {txt}" if is_sd else txt
            item = self._create_item(disp, is_header=True, align=Qt.AlignCenter)
            item.setBackground(QBrush(QColor("#f8f9fa")))
            if not is_sd: f = QFont(); f.setBold(True); item.setFont(f)
            self.table.setItem(r, 2 + i, item)

    def plot_tensile_bars(self):
        if not self.group_stats_data: self.bar_canvas.clear_plot(); return
        v = self.current_view_mode
        # [Fix] Chart parameters aligned with Table Headers (Unicode)
        if "Basic" in v:
            p = [("First Crack Strength (MPa)", "σ_cr"), ("Ultimate Stress (MPa)", "σ_u"),
                 ("Ultimate Strain (%)", "ε_tu"), ("E_eff (GPa)", "E_eff")]
        else:
            # [Fix] E_init added to Advanced Chart to match Table
            p = [("E_init (GPa)", "E_init"), ("Strain Energy (kJ/m³)", "E_v"),
                 ("Fracture Energy (kJ/m²)", "G_F"), ("Hardening Capacity (%)", "Δε_sh"),
                 ("Plateau Stability (CV)", "CV_σ")]
        grps = list(self.group_stats_data.keys());
        clean = [Path(g).stem[:15] for g in grps];
        m = {}
        for g, c in zip(grps, clean):
            s = self.group_stats_data[g];
            m[c] = {'means': [s.get(x[0] + "_mean", 0) for x in p], 'stds': [s.get(x[0] + "_sd", 0) for x in p]}
        self.bar_canvas.plot_grouped_statistics(clean, m, [x[1] for x in p])

    def _process_compressive_stats(self, keep_ids):
        grps = {}
        for r in self.current_results:
            grps.setdefault(str(r.get("Sample ID", "Unknown")).strip(), {'vals': [], 'first': r})['vals'].append(
                r.get("Peak Stress (MPa)", 0))
        self.group_stats_data = grps;
        self.table.setRowCount(len(grps));
        r = 0
        for n, d in grps.items():
            vals = np.array(d['vals']);
            mean = np.mean(vals);
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
        self.bar_canvas.clear_plot();
        clean_names = [Path(n).stem for n in names];
        means = [];
        stds = []
        for n in names:
            vals = self.group_stats_data[n]['vals']
            means.append(np.mean(vals));
            stds.append(np.std(vals, ddof=1) if len(vals) > 1 else 0)
        self.bar_canvas.plot_single_metric_bars(clean_names, means, stds, ylabel="Compressive Strength, σ (MPa)")

    def _clear_summary_row(self, r):
        for c in range(2, self.table.columnCount()): self.table.setItem(r, c, QTableWidgetItem("-"))

    def _refresh_headers(self):
        m = self.combo_mode.currentText()
        v = self.current_view_mode
        b = ["Show", "Sample"]
        # [Fix] 100% Unicode Headers (No LaTeX code)
        if "Tensile" in m:
            if "Basic" in v:
                d = ["E_eff (GPa)", "σ_cr (MPa)", "σ_u (MPa)", "ε_tu (%)"]
            else:
                d = ["E_init (GPa)", "E_v (kJ/m³)", "G_F (kJ/m²)", "Δε_sh (%)", "CV_σ"]
        else:
            d = ["σ_mean (MPa)", "SD (MPa)", "N"]
        self.table.setColumnCount(len(b) + len(d))
        self.table.setHorizontalHeaderLabels(b + d)
        self.table.setColumnWidth(0, 50)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(2, len(b) + len(d)): self.table.horizontalHeader().setSectionResizeMode(i,
                                                                                               QHeaderView.ResizeToContents)

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
            for it in items: self._add_tensile_row(it, keep_ids)
            self._add_tensile_summary_row(f, {})

    def on_row_clicked(self, it):
        pass

    def _apply_stylesheet(self):
        self.setStyleSheet(
            "QMainWindow { background: #fcfcfc } QFrame { background: white } QComboBox { padding: 2px } QTabWidget::pane { border: 0 }")

    def recalculate_all_data(self):
        self.progress.show();
        self.lbl_status.setText("Recalculating...");
        QApplication.processEvents();
        count = 0
        for res in self.current_results:
            if "raw_strain" not in res: continue
            try:
                analyzer = TensileAnalyzer(res["raw_strain"], res["raw_stress"]) if res[
                                                                                        "Type"] == "Tensile" else CompressiveAnalyzer(
                    res["raw_strain"], res["raw_stress"])
                res.update(analyzer.run_analysis());
                count += 1
            except:
                pass
        self._repopulate_table_and_charts();
        self.refresh_statistics_from_selection();
        self.progress.hide();
        self.lbl_status.setText(f"Updated {count} samples.")

    def _clear_all_data(self):
        self.table.setRowCount(0);
        self.current_results = [];
        self.group_stats_data = {};
        self.current_viewing_data = None;
        self.curve_canvas.clear_plot();
        self.curve_canvas.draw();
        self.bar_canvas.clear_plot();
        self.bar_canvas.draw();
        self.lbl_status.setText("Ready")