from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QDialogButtonBox,
    QTabWidget,
    QWidget,
    QFormLayout,
    QTextBrowser,
    QGroupBox,
    QComboBox,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import Qt
from app.core.physics import MaterialConstants


class SettingsDialog(QDialog):
    """参数设置窗口。

    当前版本把说明文字改为中文为主，保留少量英文术语，方便材料方向用户
    理解每个参数对 ECC/SHCC 拉伸曲线分析的影响。
    """

    COLOR_OPTIONS = [
        ("科研蓝 Blue (#2c3e50)", "#2c3e50"),
        ("中性灰 Gray (#7f8c8d)", "#7f8c8d"),
        ("黑色 Black (#000000)", "#000000"),
        ("红色 Red (#c0392b)", "#c0392b"),
        ("绿色 Green (#27ae60)", "#27ae60"),
    ]

    UNIT_OPTIONS = [
        ("自动判断 Auto：根据阈值判断百分数/小数", "auto"),
        ("百分数 Percent：0.5 表示 0.5%", "percent"),
        ("小数 Decimal：0.005 表示 0.5%", "decimal"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("参数设置与算法释义")
        self.resize(1020, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("ECC Analyzer Pro 参数设置")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #202124;")
        subtitle = QLabel("这里的参数会影响初裂识别、峰后极限点、应变单位换算和图表显示。建议论文正式出图前固定参数，并记录配置文件。")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #5f6368;")
        root.addWidget(title)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._create_physics_tab(), "⚙️ 参数设置")
        self.tabs.addTab(self._create_manual_tab(), "📖 指标释义")
        root.addWidget(self.tabs)

        bottom = QHBoxLayout()
        self.btn_reset = QPushButton("↺ 恢复默认参数")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self._reset_to_defaults)
        bottom.addWidget(self.btn_reset)
        bottom.addStretch()

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("保存设置")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        bottom.addWidget(self.buttons)
        root.addLayout(bottom)

        self.setStyleSheet("""
            QDialog {
                background: #ffffff;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #dadce0;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                height: 34px;
                min-width: 110px;
                padding: 0 14px;
                font-weight: 700;
                color: #5f6368;
            }
            QTabBar::tab:selected {
                color: #1a73e8;
                border-bottom: 3px solid #1a73e8;
            }
            QGroupBox {
                font-weight: 800;
                color: #202124;
                border: 1px solid #dadce0;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 22px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background: #fff;
                color: #1a73e8;
            }
            QLabel {
                color: #3c4043;
            }
            QDoubleSpinBox, QSpinBox, QComboBox {
                padding: 6px;
                border: 1px solid #dadce0;
                border-radius: 5px;
                background: #fff;
                min-height: 22px;
            }
            QDoubleSpinBox:hover, QSpinBox:hover, QComboBox:hover {
                border-color: #1a73e8;
            }
            QPushButton {
                padding: 7px 18px;
                border-radius: 6px;
                border: 1px solid #dadce0;
                background: #ffffff;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #f1f3f4;
                border-color: #bdc1c6;
            }
            QTextBrowser {
                border: none;
                background: #ffffff;
                padding: 10px;
                line-height: 1.5;
            }
        """)
        self._load_current_values()

    def _create_physics_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)

        grp_units = QGroupBox("1. 几何尺寸与应变单位 Geometry & Units")
        form_units = QFormLayout(grp_units)
        form_units.setSpacing(12)
        form_units.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.spin_gauge = self._make_double_spin(10.0, 500.0, 1.0)
        self.combo_unit = QComboBox()
        for text, _ in self.UNIT_OPTIONS:
            self.combo_unit.addItem(text)
        self.spin_strain_threshold = self._make_double_spin(0.001, 5.0, 0.01, decimals=3)

        form_units.addRow("标距 L₀ / mm：", self.spin_gauge)
        form_units.addRow("输入应变单位：", self.combo_unit)
        form_units.addRow("Auto 判断阈值：", self.spin_strain_threshold)
        layout.addWidget(grp_units)

        grp_lop = QGroupBox("2. 模量与初裂识别 Modulus & First Cracking")
        form_lop = QFormLayout(grp_lop)
        form_lop.setSpacing(12)
        form_lop.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.spin_elas_lower = self._make_double_spin(0.0, 1.0, 0.05)
        self.spin_elas_upper = self._make_double_spin(0.0, 1.0, 0.05)
        self.spin_crack_tol = self._make_double_spin(0.001, 1.0, 0.005, decimals=3)
        self.spin_crack_ratio = self._make_double_spin(0.0, 0.2, 0.005, decimals=3)
        self.spin_stiffness = self._make_double_spin(0.1, 1.0, 0.01)
        self.spin_min_stress = self._make_double_spin(0.0, 0.5, 0.01)

        form_lop.addRow("有效模量下限比例：", self.spin_elas_lower)
        form_lop.addRow("有效模量上限比例：", self.spin_elas_upper)
        form_lop.addRow("初裂偏离基准 / MPa：", self.spin_crack_tol)
        form_lop.addRow("初裂偏离比例：", self.spin_crack_ratio)
        form_lop.addRow("刚度下降约束：", self.spin_stiffness)
        form_lop.addRow("初裂最小应力比例：", self.spin_min_stress)
        layout.addWidget(grp_lop)

        grp_signal = QGroupBox("3. 峰后极限与绘图 Failure & Visualization")
        form_signal = QFormLayout(grp_signal)
        form_signal.setSpacing(12)
        form_signal.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.spin_ult_ratio = self._make_double_spin(0.50, 1.00, 0.01)
        self.spin_smooth = QSpinBox()
        self.spin_smooth.setRange(3, 101)
        self.spin_smooth.setSingleStep(2)
        self.spin_line_width = self._make_double_spin(0.5, 5.0, 0.5)
        self.combo_color = QComboBox()
        for text, _ in self.COLOR_OPTIONS:
            self.combo_color.addItem(text)

        form_signal.addRow("峰后失效比例：", self.spin_ult_ratio)
        form_signal.addRow("平滑窗口点数：", self.spin_smooth)
        form_signal.addRow("曲线线宽 / px：", self.spin_line_width)
        form_signal.addRow("默认曲线颜色：", self.combo_color)
        layout.addWidget(grp_signal)

        tip = QLabel("提示：如果不确定参数含义，建议先保持默认值；正式论文出图前再根据试验曲线稳定性微调。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #5f6368; background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px;")
        layout.addWidget(tip)
        layout.addStretch()
        return widget

    def _create_manual_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        viewer = QTextBrowser()
        viewer.setOpenExternalLinks(True)
        viewer.setHtml("""
        <h2>参数和指标怎么理解</h2>
        <p>这页不是严格的理论教材，而是给软件使用者看的说明。核心目标是：知道每个参数会影响什么，避免把单位或指标理解错。</p>

        <h3>一、应变单位</h3>
        <p><b>Input Strain Unit</b> 决定程序如何读取 Excel 里的应变列。</p>
        <ul>
          <li><b>Percent：</b>适合表头写 <code>Strain (%)</code> 的数据，输入 <code>0.5</code> 表示 <code>0.5%</code>。</li>
          <li><b>Decimal：</b>适合 DIC 或程序导出的小数应变，输入 <code>0.005</code> 表示 <code>0.5%</code>。</li>
          <li><b>Auto：</b>根据阈值自动判断。默认阈值为 <code>0.2</code>，大于该值更可能被当作百分数。</li>
        </ul>
        <p><b>建议：</b>如果你的表头明确写了百分号，优先选 Percent，不要完全依赖 Auto。</p>

        <h3>二、有效模量 E<sub>eff</sub></h3>
        <p>软件默认在峰值应力的某个比例区间内做线性回归，例如 10%–40% σ<sub>u</sub>。
        这个值更像工程上的有效刚度，适合不同试件之间对比。</p>

        <h3>三、初裂强度 σ<sub>cr</sub></h3>
        <p>初裂点不是靠肉眼点出来的，而是同时考虑三件事：</p>
        <ol>
          <li>曲线相对线性段发生明显偏离；</li>
          <li>局部切线刚度出现下降；</li>
          <li>当前应力已经达到一定比例，避免把起始噪声误判为初裂。</li>
        </ol>
        <p>如果曲线噪声很大，可以适当增大“初裂偏离基准”或“初裂偏离比例”。</p>

        <h3>四、峰值应变 ε<sub>peak</sub> 与极限应变 ε<sub>u</sub></h3>
        <p>这两个指标必须分开：</p>
        <ul>
          <li><b>ε<sub>peak</sub>：</b>峰值拉伸强度 σ<sub>u</sub> 对应的应变；</li>
          <li><b>ε<sub>u</sub>：</b>峰后应力持续下降到设定比例后的极限/失效应变。</li>
        </ul>
        <p>ECC/SHCC 往往有多缝开展和纤维桥接过程，峰值点不一定等于真正的变形终点。</p>

        <h3>五、峰后失效比例</h3>
        <p>峰后失效比例用于寻找 ε<sub>u</sub>。例如设为 <code>0.85</code>，表示峰后应力持续低于
        <code>0.85 × σ<sub>u</sub></code> 后，可认为进入极限/失效区间。数值越高，ε<sub>u</sub> 越靠近峰值点；数值越低，ε<sub>u</sub> 越靠后。</p>

        <h3>六、断裂能指标 G<sub>F</sub></h3>
        <p>软件对 <code>0 → ε<sub>u</sub></code> 的应力-应变曲线积分，并乘以标距 L<sub>0</sub>，得到一个用于组间比较的能量指标。
        这个指标适合在同一试验制度、同一标距、同一数据处理参数下横向比较。</p>

        <h3>七、抗压模式</h3>
        <p>如果抗压应力在原始数据里是负数，程序默认会转成正的强度大小。这样导出的抗压强度更符合论文表格习惯。</p>

        <h3>八、建议记录的参数</h3>
        <p>用于论文或组会时，建议记录：Input Strain Unit、Gauge Length、Elastic Fit 区间、Crack Tolerance、Rupture Ratio、Smoothing Window。</p>
        """)
        layout.addWidget(viewer)
        return widget

    def _make_double_spin(self, min_val, max_val, step, decimals=2):
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setFixedWidth(170)
        return spin

    def _index_for_value(self, options, value, default=0):
        for i, (_, opt_value) in enumerate(options):
            if str(opt_value).lower() == str(value).lower():
                return i
        return default

    def get_values(self):
        unit = self.UNIT_OPTIONS[self.combo_unit.currentIndex()][1]
        color = self.COLOR_OPTIONS[self.combo_color.currentIndex()][1]
        smooth = int(self.spin_smooth.value())
        if smooth % 2 == 0:
            smooth += 1

        return {
            "GAUGE_LENGTH_MM": self.spin_gauge.value(),
            "STRAIN_UNIT": unit,
            "STRAIN_PERCENT_THRESHOLD": self.spin_strain_threshold.value(),
            "ELASTIC_LOWER_RATIO": self.spin_elas_lower.value(),
            "ELASTIC_UPPER_RATIO": self.spin_elas_upper.value(),
            "CRACK_TOLERANCE_BASE": self.spin_crack_tol.value(),
            "CRACK_TOLERANCE_RATIO": self.spin_crack_ratio.value(),
            "CRACK_STIFFNESS_CONSTRAINT": self.spin_stiffness.value(),
            "CRACK_MIN_STRESS_RATIO": self.spin_min_stress.value(),
            "ULTIMATE_STRAIN_RATIO": self.spin_ult_ratio.value(),
            "SMOOTH_WINDOW": smooth,
            "STYLE_LINE_WIDTH": self.spin_line_width.value(),
            "STYLE_COLOR_RAW": color,
            "STYLE_COLOR_SMOOTH": color,
        }

    def _load_current_values(self):
        MaterialConstants.load_config()
        self.spin_gauge.setValue(MaterialConstants.GAUGE_LENGTH_MM)
        self.combo_unit.setCurrentIndex(self._index_for_value(self.UNIT_OPTIONS, getattr(MaterialConstants, "STRAIN_UNIT", "auto")))
        self.spin_strain_threshold.setValue(getattr(MaterialConstants, "STRAIN_PERCENT_THRESHOLD", 0.2))
        self.spin_elas_lower.setValue(MaterialConstants.ELASTIC_LOWER_RATIO)
        self.spin_elas_upper.setValue(MaterialConstants.ELASTIC_UPPER_RATIO)
        self.spin_crack_tol.setValue(MaterialConstants.CRACK_TOLERANCE_BASE)
        self.spin_crack_ratio.setValue(getattr(MaterialConstants, "CRACK_TOLERANCE_RATIO", 0.01))
        self.spin_stiffness.setValue(getattr(MaterialConstants, "CRACK_STIFFNESS_CONSTRAINT", 0.85))
        self.spin_min_stress.setValue(getattr(MaterialConstants, "CRACK_MIN_STRESS_RATIO", 0.10))
        self.spin_ult_ratio.setValue(getattr(MaterialConstants, "ULTIMATE_STRAIN_RATIO", 0.85))
        self.spin_smooth.setValue(int(MaterialConstants.SMOOTH_WINDOW))
        self.spin_line_width.setValue(getattr(MaterialConstants, "STYLE_LINE_WIDTH", 1.5))
        self.combo_color.setCurrentIndex(self._index_for_value(self.COLOR_OPTIONS, getattr(MaterialConstants, "STYLE_COLOR_RAW", "#2c3e50")))

    def _reset_to_defaults(self):
        MaterialConstants.reset_defaults()
        self._load_current_values()
        QMessageBox.information(self, "已恢复默认参数", "参数已恢复为默认值，点击“保存设置”后生效。")

    def accept(self):
        if self.spin_elas_lower.value() >= self.spin_elas_upper.value():
            QMessageBox.warning(self, "参数不合理", "有效模量下限比例必须小于上限比例。")
            return
        values = self.get_values()
        MaterialConstants.update_config(**values)
        super().accept()
