from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QApplication,
    QHeaderView,
    QSplitter,
    QPushButton,
    QLabel,
    QMenu,
)
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtCore import Qt

from app.ui.main_window import MainWindow as _BaseMainWindow, ViewSwitcher as _BaseViewSwitcher
from app.data.exporter import DataExporter
from app.core.statistics import StatisticsCalculator
from app.core.physics import MaterialConstants


class MainWindow(_BaseMainWindow):
    """正式运行主窗口。

    app.ui.main_window.MainWindow 保留为基础窗口实现，本类集中维护当前真正生效的
    UI/UX 行为。这样既不需要一次性重写 900 多行主窗口，又能保证用户看到的是
    干净、中文化、Qt 兼容的界面。
    """

    def __init__(self):
        self._patch_qss_compatibility()
        super().__init__()
        self._apply_active_layout_adjustments()
        self._localize_base_ui_texts()

    def _patch_qss_compatibility(self):
        """Remove unsupported CSS properties before the base UI is created.

        Qt Style Sheet (QSS) is not full web CSS. Properties such as
        ``box-shadow`` will trigger repeated "Unknown property box-shadow" warnings.
        This monkey patch keeps the segmented switcher visual style while using
        QSS-supported properties only.
        """

        def _create_btn_qt_safe(view_switcher, text):
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

        _BaseViewSwitcher._create_btn = _create_btn_qt_safe

    def _apply_active_layout_adjustments(self):
        """Widen the data panel for the five-column Basic tensile table."""
        try:
            splitters = self.findChildren(QSplitter)
            if splitters:
                splitter = splitters[0]
                left = splitter.widget(0)
                if left is not None:
                    left.setMinimumWidth(640)
                splitter.setSizes([700, 740])
        except Exception:
            pass

    def _localize_base_ui_texts(self):
        """Localize visible UI text to Chinese while keeping key English terms."""
        self.setWindowTitle("ECC Analyzer Pro｜ECC/SHCC 力学数据分析")

        # Header labels created in the base class are not all stored as attributes,
        # so update them by their visible text.
        for label in self.findChildren(QLabel):
            if label.text() == "Mode:":
                label.setText("模式：")
            elif label.text() == "Theme:":
                label.setText("配色：")

        self.combo_mode.blockSignals(True)
        current_index = self.combo_mode.currentIndex()
        self.combo_mode.clear()
        self.combo_mode.addItems(["抗拉 Tensile", "抗压 Compressive"])
        self.combo_mode.setCurrentIndex(max(0, current_index))
        self.combo_mode.blockSignals(False)

        if hasattr(self, "view_switcher"):
            self.view_switcher.btn_basic.setText("基础结果")
            self.view_switcher.btn_adv.setText("高级分析")

        if hasattr(self, "drop_zone"):
            self.drop_zone.lbl_main.setText("导入试验数据")
            self.drop_zone.lbl_sub.setText("拖拽 .xlsx / .csv 文件到这里\n或点击选择文件")

        if hasattr(self, "btn_export"):
            self.btn_export.setText("💾 导出报告")
        if hasattr(self, "btn_settings"):
            self.btn_settings.setText("⚙️ 参数设置")
        if hasattr(self, "btn_clear"):
            self.btn_clear.setText("🗑️ 清空")
        if hasattr(self, "btn_all"):
            self.btn_all.setText("☑ 全选")

        for btn in self.findChildren(QPushButton):
            text = btn.text().strip()
            replacements = {
                "🔄 Calc": "🔄 重新计算",
                "📋 Copy": "📋 复制表格",
                "🗑️ Del": "🗑️ 删除勾选",
                "📷 Save Image": "📷 保存图片",
            }
            if text in replacements:
                btn.setText(replacements[text])

        if hasattr(self, "tabs"):
            self.tabs.setTabText(0, "📊 统计图")
            self.tabs.setTabText(1, "📈 曲线图")

        if hasattr(self, "chk_params"):
            self.chk_params.setText("显示参数标注")

        if hasattr(self, "combo_color_main"):
            self.combo_color_main.blockSignals(True)
            current_color = self.combo_color_main.currentIndex()
            self.combo_color_main.clear()
            self.combo_color_main.addItems(["科研蓝", "中性灰", "黑色", "红色", "绿色"])
            self.combo_color_main.setCurrentIndex(max(0, current_color))
            self.combo_color_main.blockSignals(False)

        self.lbl_status.setText("就绪")

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
