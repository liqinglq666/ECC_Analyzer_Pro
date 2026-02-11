from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QDoubleSpinBox, QDialogButtonBox, QTabWidget,
                               QWidget, QFormLayout, QTextBrowser, QGroupBox,
                               QComboBox, QPushButton, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from app.core.physics import MaterialConstants


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration & Constitutive Manual (设置与本构说明)")
        self.resize(1100, 800)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # --- Tabs ---
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        # 现代化 Tab 样式
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #e0e0e0; border-radius: 6px; background: #fff; top: -1px; }
            QTabBar::tab { 
                height: 32px; width: 180px; font-weight: 600; color: #5f6368; 
                font-family: 'Segoe UI'; border: 1px solid transparent; 
                border-bottom: none; margin-right: 4px;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected { 
                color: #1a73e8; background: #fff; 
                border-color: #e0e0e0; border-bottom-color: #fff; 
            }
            QTabBar::tab:hover:!selected { background: #f1f3f4; }
        """)

        self.tabs.addTab(self._create_physics_tab(), "⚙️ Parameters (参数)")
        self.tabs.addTab(self._create_manual_tab(), "📖 Dictionary (释义)")
        self.layout.addWidget(self.tabs)

        # --- Bottom Bar ---
        bottom_layout = QHBoxLayout()

        # Reset Button
        self.btn_reset = QPushButton("↺ Reset Defaults")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet("""
            QPushButton { color: #d93025; background: transparent; border: none; font-weight: bold; }
            QPushButton:hover { background: #fce8e6; border-radius: 4px; }
        """)
        self.btn_reset.clicked.connect(self._reset_to_defaults)
        bottom_layout.addWidget(self.btn_reset)

        bottom_layout.addStretch()

        # Action Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # 谷歌 Material Design 风格按钮
        self.buttons.setStyleSheet("""
            QPushButton { padding: 6px 24px; border-radius: 4px; font-weight: 600; font-family: 'Segoe UI'; font-size: 13px; }
            QPushButton[text="OK"] { background-color: #1a73e8; color: white; border: none; }
            QPushButton[text="OK"]:hover { background-color: #1557b0; }
            QPushButton[text="Cancel"] { background-color: white; border: 1px solid #dadce0; color: #3c4043; }
            QPushButton[text="Cancel"]:hover { background-color: #f8f9fa; color: #202124; }
        """)
        bottom_layout.addWidget(self.buttons)

        self.layout.addLayout(bottom_layout)

        self._load_current_values()

    def _create_physics_tab(self):
        """参数设置面板"""
        scroll_widget = QWidget()
        # 白色背景卡片风格
        scroll_widget.setStyleSheet("background-color: #ffffff;")
        main_layout = QVBoxLayout(scroll_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)

        # --- Group 1: Constitutive Model Parameters ---
        grp_analysis = QGroupBox("1. Constitutive Parameters (本构模型参数)")
        grp_analysis.setStyleSheet("""
            QGroupBox { font-weight: 700; color: #202124; border: 1px solid #dadce0; border-radius: 8px; margin-top: 12px; padding-top: 24px; font-size: 13px; } 
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; background: #fff; color: #1a73e8; }
        """)
        layout_ana = QFormLayout(grp_analysis)
        layout_ana.setLabelAlignment(Qt.AlignRight)
        layout_ana.setSpacing(15)

        self.spin_gauge = self._make_spin(10.0, 500.0, 1.0)
        self.spin_gauge.setToolTip(
            "Gauge Length (L0)\n建议值: 80.0 mm (哑铃型) / 150.0 mm (棱柱体)\n直接决定断裂能(G_F)和应变(ε)的计算精度，请务必输入实测标距。")
        layout_ana.addRow("Gauge Length (L₀, mm):", self.spin_gauge)

        self.spin_elas_lower = self._make_spin(0.0, 1.0, 0.05)
        self.spin_elas_upper = self._make_spin(0.0, 1.0, 0.05)
        self.spin_elas_lower.setToolTip(
            "Regression Start\n建议值: 0.10 (10% Peak Stress)\n工程模量(E_eff)线性回归的起始点。")
        self.spin_elas_upper.setToolTip(
            "Regression End\n建议值: 0.40 (40% Peak Stress)\n工程模量(E_eff)线性回归的终止点。")
        layout_ana.addRow("Elastic Fit Lower (Ratio):", self.spin_elas_lower)
        layout_ana.addRow("Elastic Fit Upper (Ratio):", self.spin_elas_upper)

        self.spin_crack_tol = self._make_spin(0.001, 0.5, 0.005, decimals=3)
        self.spin_crack_tol.setToolTip(
            "LOP Tolerance\n建议值: 0.05 MPa\n首裂主判据。当实际应力偏离理论线弹性轨迹超过此阈值时，触发损伤起始预警。")
        layout_ana.addRow("Crack Tolerance (MPa):", self.spin_crack_tol)

        self.spin_ult_ratio = self._make_spin(0.50, 1.00, 0.01)
        self.spin_ult_ratio.setToolTip(
            "Failure Criterion\n建议值: 0.85\n失效判据。当峰后应力衰减至峰值的 85% 时，判定为材料宏观断裂(Rupture)。")
        layout_ana.addRow("Rupture Ratio (Post-Peak):", self.spin_ult_ratio)

        main_layout.addWidget(grp_analysis)

        # --- Group 2: Visualization ---
        grp_vis = QGroupBox("2. Signal & Visualization (信号与绘图)")
        grp_vis.setStyleSheet(grp_analysis.styleSheet())
        layout_vis = QFormLayout(grp_vis)

        self.combo_color = QComboBox()
        self.combo_color.addItems(
            ["Scientific Blue (#2c3e50)", "Classic Gray (#7f8c8d)", "Deep Black (#000000)", "Crimson Red (#c0392b)",
             "Emerald Green (#27ae60)"])
        self.combo_color.setFixedWidth(200)
        self.combo_color.setStyleSheet("""
            QComboBox { padding: 4px; border: 1px solid #bdc3c7; border-radius: 4px; }
            QComboBox::drop-down { border: 0px; }
        """)
        layout_vis.addRow("Default Curve Color:", self.combo_color)

        self.spin_smooth = self._make_spin(1, 51, 2, decimals=0)
        self.spin_smooth.setToolTip(
            "Savitzky-Golay Window\n建议值: 5 - 15 (必须为奇数)\n用于初始模量计算的微分平滑窗口。")
        layout_vis.addRow("Smoothing Window (Points):", self.spin_smooth)

        # UI 上已移除 Width 控件，这里保留作为全局默认值设置
        self.spin_line_width = self._make_spin(0.5, 5.0, 0.5)
        layout_vis.addRow("Base Line Width (px):", self.spin_line_width)

        main_layout.addWidget(grp_vis)
        main_layout.addStretch()

        return scroll_widget

    def _create_manual_tab(self):
        """[Scientific] 专业术语手册"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        manual_viewer = QTextBrowser()
        manual_viewer.setOpenExternalLinks(True)

        # 仿论文排版 CSS
        manual_viewer.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff; 
                padding: 40px; 
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                font-size: 14px;
                line-height: 1.6;
                color: #202124;
                border: none;
            }
            h2 { 
                color: #202124; 
                border-bottom: 2px solid #1a73e8; 
                padding-bottom: 10px; 
                margin-top: 0; margin-bottom: 25px;
                font-family: 'Segoe UI Semibold';
                font-size: 20px;
            }
            h3 { 
                color: #1a73e8; 
                margin-top: 30px; 
                margin-bottom: 15px; 
                font-size: 15px; 
                font-weight: 700; 
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .term-box {
                border-left: 3px solid #e8eaed;
                padding-left: 15px;
                margin-bottom: 20px;
            }
            .term-title {
                color: #202124;
                font-weight: 700;
                font-size: 14px;
                margin-bottom: 4px;
                display: block;
            }
            .symbol {
                font-family: 'Times New Roman', serif;
                font-style: italic;
                font-weight: bold;
                color: #d93025;
            }
            .desc { color: #5f6368; }
            .highlight {
                background-color: #f1f3f4;
                padding: 1px 4px;
                border-radius: 2px;
                font-size: 13px;
                color: #3c4043;
            }
            hr { border: 0; border-top: 1px solid #f1f3f4; margin: 40px 0; }
        """)

        html_content = """
        <h2>📘 Constitutive Parameters (本构参数定义)</h2>
        <p style="color:#5f6368;">This manual defines the key mechanical indicators used in the analysis, strictly following RILEM TC-208-HFC and JSCE recommendations.</p>

        <h3>1. Stiffness & Elasticity (刚度与弹性)</h3>

        <div class="term-box">
            <span class="term-title"><span class="symbol">E<sub>eff</sub></span> &nbsp; Effective Modulus (有效模量)</span>
            <span class="desc">The secant stiffness used for structural engineering design. Calculated via linear regression within the <span class="highlight">10% - 40%</span> peak stress range.</span>
        </div>

        <div class="term-box">
            <span class="term-title"><span class="symbol">σ<sub>cr</sub></span> &nbsp; First Cracking Strength (初裂强度)</span>
            <span class="desc">The stress at the Limit of Proportionality (LOP). It marks the transition from linear elasticity to the multiple-cracking stage. Detected when stress deviates from linearity by <span class="highlight">> 0.05 MPa</span>.</span>
        </div>

        <h3>2. Strength & Ductility (强度与延性)</h3>

        <div class="term-box">
            <span class="term-title"><span class="symbol">σ<sub>u</sub></span> &nbsp; Ultimate Strength (极限强度)</span>
            <span class="desc">The maximum stress capacity (Peak Stress) of the composite before strain localization or rupture.</span>
        </div>

        <div class="term-box">
            <span class="term-title"><span class="symbol">ε<sub>tu</sub></span> &nbsp; Ultimate Strain (极限应变)</span>
            <span class="desc">The strain capacity corresponding to the peak stress. Represents the ductility of the material.</span>
        </div>

        <div class="term-box">
            <span class="term-title"><span class="symbol">Δε<sub>sh</sub></span> &nbsp; Strain-Hardening Capacity (硬化容量)</span>
            <span class="desc">Defined as <span class="symbol">ε<sub>tu</sub> - ε<sub>cr</sub></span>. This metric purely quantifies the multiple-cracking potential, excluding elastic deformation.</span>
        </div>

        <h3>3. Energy & Stability (能量与稳定性)</h3>

        <div class="term-box">
            <span class="term-title"><span class="symbol">G<sub>F</sub></span> &nbsp; Fracture Energy (断裂能)</span>
            <span class="desc">Energy dissipated per unit area of the fracture surface up to the failure point. Unit: <span class="highlight">kJ/m²</span>.</span>
        </div>

        <div class="term-box">
            <span class="term-title"><span class="symbol">CV<sub>σ</sub></span> &nbsp; Plateau Stability (平台稳定性)</span>
            <span class="desc">Coefficient of Variation of stress in the hardening region. A lower value indicates a more stable, flat-top strain hardening behavior.</span>
        </div>

        <hr>
        <div style="text-align: right; color: #bdc1c6; font-size: 11px;">
            Algorithm Version: Scientific V23.18
        </div>
        """

        manual_viewer.setHtml(html_content)
        layout.addWidget(manual_viewer)
        return widget

    def _make_spin(self, min_val, max_val, step, decimals=2):
        sb = QDoubleSpinBox()
        sb.setRange(min_val, max_val)
        sb.setSingleStep(step)
        sb.setDecimals(decimals)
        sb.setFixedWidth(120)
        # 现代化 Flat 风格
        sb.setStyleSheet("""
            QDoubleSpinBox { 
                padding: 6px; border: 1px solid #dadce0; border-radius: 4px; background: #fff; font-family: 'Segoe UI'; 
            } 
            QDoubleSpinBox:focus { border: 2px solid #1a73e8; padding: 5px; }
            QDoubleSpinBox:hover { border: 1px solid #202124; }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0px; border: none; } /* 隐藏丑陋的微调按钮，倾向于键盘输入或滚轮 */
        """)
        return sb

    def _reset_to_defaults(self):
        """恢复默认值"""
        self.spin_gauge.setValue(80.0)
        self.spin_elas_lower.setValue(0.10)
        self.spin_elas_upper.setValue(0.40)
        self.spin_crack_tol.setValue(0.05)
        self.spin_ult_ratio.setValue(0.85)
        self.spin_smooth.setValue(11)
        self.spin_line_width.setValue(1.5)
        self.combo_color.setCurrentIndex(0)

    def get_values(self):
        """返回所有配置项"""
        # 映射回十六进制颜色
        c_index = self.combo_color.currentIndex()
        c_map = ["#2c3e50", "#7f8c8d", "#000000", "#c0392b", "#27ae60"]
        selected_color = c_map[c_index] if c_index < len(c_map) else "#2c3e50"

        return {
            "GAUGE_LENGTH_MM": self.spin_gauge.value(),
            "ELASTIC_LOWER_RATIO": self.spin_elas_lower.value(),
            "ELASTIC_UPPER_RATIO": self.spin_elas_upper.value(),
            "CRACK_TOLERANCE_BASE": self.spin_crack_tol.value(),
            "ULTIMATE_STRAIN_RATIO": self.spin_ult_ratio.value(),
            "SMOOTH_WINDOW": int(self.spin_smooth.value()),
            # Visualization
            "STYLE_LINE_WIDTH": self.spin_line_width.value(),
            "STYLE_COLOR_RAW": selected_color
        }

    def _load_current_values(self):
        """加载当前参数"""
        self.spin_gauge.setValue(MaterialConstants.GAUGE_LENGTH_MM)
        self.spin_elas_lower.setValue(MaterialConstants.ELASTIC_LOWER_RATIO)
        self.spin_elas_upper.setValue(MaterialConstants.ELASTIC_UPPER_RATIO)
        self.spin_crack_tol.setValue(MaterialConstants.CRACK_TOLERANCE_BASE)

        val_ult = getattr(MaterialConstants, "ULTIMATE_STRAIN_RATIO", 0.85)
        self.spin_ult_ratio.setValue(val_ult)

        self.spin_smooth.setValue(MaterialConstants.SMOOTH_WINDOW)

        val_lw = getattr(MaterialConstants, "STYLE_LINE_WIDTH", 1.5)
        self.spin_line_width.setValue(val_lw)

        val_col = getattr(MaterialConstants, "STYLE_COLOR_RAW", "#2c3e50")

        # 颜色反向映射
        c_map = ["#2c3e50", "#7f8c8d", "#000000", "#c0392b", "#27ae60"]
        try:
            idx = c_map.index(val_col)
        except ValueError:
            idx = 0
        self.combo_color.setCurrentIndex(idx)