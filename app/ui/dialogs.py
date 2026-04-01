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

        self.btn_reset = QPushButton("↺ Reset Defaults")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet("""
            QPushButton { color: #d93025; background: transparent; border: none; font-weight: bold; }
            QPushButton:hover { background: #fce8e6; border-radius: 4px; }
        """)
        self.btn_reset.clicked.connect(self._reset_to_defaults)
        bottom_layout.addWidget(self.btn_reset)

        bottom_layout.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

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
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: #ffffff;")
        main_layout = QVBoxLayout(scroll_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)

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
            "Gauge Length (L₀)\n直接决定断裂能 (G_F) 的积分转换。请务必输入 LVDT 实际测点间的标距跨度。")
        layout_ana.addRow("Gauge Length (L₀, mm):", self.spin_gauge)

        self.spin_elas_lower = self._make_spin(0.0, 1.0, 0.05)
        self.spin_elas_upper = self._make_spin(0.0, 1.0, 0.05)
        layout_ana.addRow("Elastic Fit Lower (Ratio):", self.spin_elas_lower)
        layout_ana.addRow("Elastic Fit Upper (Ratio):", self.spin_elas_upper)

        self.spin_crack_tol = self._make_spin(0.001, 0.5, 0.005, decimals=3)
        self.spin_crack_tol.setToolTip(
            "LOP Tolerance (δ_tol)\n首裂判据的基础偏离容差。实际算法中采用了刚度衰减与偏离量的多重耦合判据以抵抗噪音。")
        layout_ana.addRow("Crack Tolerance (MPa):", self.spin_crack_tol)

        self.spin_ult_ratio = self._make_spin(0.50, 1.00, 0.01)
        self.spin_ult_ratio.setToolTip(
            "Failure Criterion (γ)\n峰后应力跌落判定阈值。默认 0.85 即代表应力跌至峰值的 85% 时判定为宏观失效限点 (Limit Point)。")
        layout_ana.addRow("Rupture Ratio (Post-Peak):", self.spin_ult_ratio)

        main_layout.addWidget(grp_analysis)

        grp_vis = QGroupBox("2. Signal & Visualization (信号与绘图)")
        grp_vis.setStyleSheet(grp_analysis.styleSheet())
        layout_vis = QFormLayout(grp_vis)

        self.combo_color = QComboBox()
        self.combo_color.addItems(
            ["Scientific Blue (#2c3e50)", "Classic Gray (#7f8c8d)", "Deep Black (#000000)", "Crimson Red (#c0392b)",
             "Emerald Green (#27ae60)"])
        self.combo_color.setFixedWidth(200)
        self.combo_color.setStyleSheet(
            "QComboBox { padding: 4px; border: 1px solid #bdc3c7; border-radius: 4px; } QComboBox::drop-down { border: 0px; }")
        layout_vis.addRow("Default Curve Color:", self.combo_color)

        self.spin_smooth = self._make_spin(1, 51, 2, decimals=0)
        self.spin_smooth.setToolTip(
            "Savitzky-Golay Window\n用于求解真实初始切线模量 E_init 的数值微分平滑窗口大小。必须为奇数。")
        layout_vis.addRow("Smoothing Window (Points):", self.spin_smooth)

        self.spin_line_width = self._make_spin(0.5, 5.0, 0.5)
        layout_vis.addRow("Base Line Width (px):", self.spin_line_width)

        main_layout.addWidget(grp_vis)
        main_layout.addStretch()

        return scroll_widget

    def _create_manual_tab(self):
        """[Scientific] 完全对齐底层鲁棒算法的中文手册"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        manual_viewer = QTextBrowser()
        manual_viewer.setOpenExternalLinks(True)

        manual_viewer.setStyleSheet("""
            QTextBrowser { background-color: #ffffff; padding: 40px; font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.6; color: #202124; border: none; }
            h2 { color: #202124; border-bottom: 2px solid #1a73e8; padding-bottom: 8px; margin-top: 0; margin-bottom: 20px; font-family: 'Segoe UI Semibold', 'Microsoft YaHei'; font-size: 18px; }
            h3 { color: #1a73e8; margin-top: 25px; margin-bottom: 12px; font-size: 15px; font-weight: 700; letter-spacing: 0.5px; }
            .term-box { border-left: 3px solid #e8eaed; padding-left: 15px; margin-bottom: 22px; }
            .term-title { color: #202124; font-weight: 700; font-size: 14px; margin-bottom: 4px; display: block; }
            .symbol { font-family: 'Times New Roman', serif; font-style: italic; font-weight: bold; color: #d93025; }
            .desc { color: #5f6368; display: block; margin-bottom: 6px; }
            .formula { background-color: #f8f9fa; padding: 6px 10px; font-family: 'Times New Roman', serif; font-size: 14px; color: #0f9d58; border: 1px solid #e8eaed; }
            hr { border: 0; border-top: 1px solid #f1f3f4; margin: 30px 0; }
        """)

        html_content = """
        <h2>📘 算法架构与物理量定义 (Algorithms & Metrics)</h2>
        <p style="color:#5f6368;">本软件内置了抗噪型物理引擎 (Robust Physics Engine)。针对真实实验中存在的夹具滑动与测试噪音，本工具对传统材料力学的特征点提取逻辑进行了强健的工程化改造，确保指标具有极高的重现性。</p>

        <h3>1. 模量提取与首裂判据 (Stiffness & LOP)</h3>

        <div class="term-box">
            <span class="term-title"><span class="symbol">E<sub>eff</sub></span> &nbsp; 有效割线模量 (Effective Secant Modulus)</span>
            <span class="desc">排除初始试件对中误差后，代表材料真实刚度的宏观线弹性模量。采用预设区间（默认 10%至 40% 峰值应力）的最小二乘法进行线性回归。</span>
        </div>

        <div class="term-box">
            <span class="term-title"><span class="symbol">σ<sub>cr</sub></span> &nbsp; 初裂强度 (First Cracking Strength)</span>
            <span class="desc">为了抵抗实验早期的信号震荡，本软件采用了<b>多重耦合防误判逻辑</b>，而非单一容差。仅当同时满足以下三个条件时，确认基体开裂：</span>
            <ul style="color:#5f6368; margin-top:0px; margin-bottom:6px; padding-left:20px;">
                <li><b>线性偏离：</b> 实际应力向下偏离理论线弹性轨迹 > Max(δ<sub>tol</sub>, 1% σ<sub>u</sub>)</li>
                <li><b>刚度衰减：</b> 实时切线模量实质性退化至初始峰值模量 (E<sub>init</sub>) 的 85% 以下</li>
                <li><b>底层过滤：</b> 触发点应力必须大于 10% 峰值应力，屏蔽底噪</li>
            </ul>
        </div>

        <h3>2. 极限失效与硬化容量 (Failure & Ductility)</h3>

        <div class="term-box">
            <span class="term-title"><span class="symbol">σ<sub>u</sub></span> &nbsp; 极限拉伸强度 (Peak Stress)</span>
            <span class="desc">测试过程中的绝对最大应力值 (Maximum Stress Capacity)。</span>
            <div class="formula"><b>计算公式:</b> &nbsp; <i>σ<sub>u</sub> = max(σ(ε))</i></div>
        </div>

        <div class="term-box">
            <span class="term-title"><span class="symbol">ε<sub>u</sub></span> &nbsp; 宏观失效极限应变 (Limit / Failure Strain)</span>
            <span class="desc"><b>[核心机制]</b> ECC 材料在达到峰值应力后，往往依靠纤维桥接仍具备可观的变形与承载能力。本算法采用前瞻探测 (Look-Ahead) 机制，追踪峰后应力实质性跌破预设比例阈值（γ，默认 85% σ<sub>u</sub>）的位置，将其定义为真实的失效极限应变。若未跌破，则取曲线终点。</span>
        </div>

        <div class="term-box">
            <span class="term-title"><span class="symbol">Δε<sub>sh</sub></span> &nbsp; 应变硬化容量 (Strain-Hardening Capacity)</span>
            <span class="desc">量化多缝开裂的纯塑性变形能力。为了真实反映材料至失效前的延展性，使用失效极限应变扣除初裂应变。</span>
            <div class="formula"><b>计算公式:</b> &nbsp; <i>Δε<sub>sh</sub> = ε<sub>u</sub> - ε<sub>cr</sub></i></div>
        </div>

        <h3>3. 能量耗散与裂缝控制 (Energy & Stability)</h3>

        <div class="term-box">
            <span class="term-title"><span class="symbol">G<sub>F</sub></span> &nbsp; 断裂能 (Fracture Energy)</span>
            <span class="desc">采用辛普森法则 (Simpson's Rule)，对 0 到失效极限点 (<span class="symbol">ε<sub>u</sub></span>) 的应力-应变曲线进行全路径高精度数值积分，并按用户输入的标距换算得到。</span>
        </div>

        <div class="term-box">
            <span class="term-title"><span class="symbol">CV<sub>σ</sub></span> &nbsp; 平台稳定性 (Plateau Stability)</span>
            <span class="desc">计算应力响应在硬化区间 [<span class="symbol">ε<sub>cr</sub>, ε<sub>u</sub></span>] 内的变异系数。值越低，多缝开裂越均匀稳态。</span>
            <div class="formula"><b>计算公式:</b> &nbsp; <i>CV<sub>σ</sub> = SD(σ<sub>sh</sub>) / Mean(σ<sub>sh</sub>)</i></div>
        </div>

        <hr>
        <div style="text-align: right; color: #bdc1c6; font-size: 11px;">
            Robust Physics Engine Build: 2.1 (Multi-Criteria LOP & Post-Peak Tracking)
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
        sb.setStyleSheet("""
            QDoubleSpinBox { padding: 6px; border: 1px solid #dadce0; border-radius: 4px; background: #fff; font-family: 'Segoe UI'; } 
            QDoubleSpinBox:focus { border: 2px solid #1a73e8; padding: 5px; }
            QDoubleSpinBox:hover { border: 1px solid #202124; }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0px; border: none; }
        """)
        return sb

    def _reset_to_defaults(self):
        self.spin_gauge.setValue(80.0)
        self.spin_elas_lower.setValue(0.10)
        self.spin_elas_upper.setValue(0.40)
        self.spin_crack_tol.setValue(0.05)
        self.spin_ult_ratio.setValue(0.85)
        self.spin_smooth.setValue(11)
        self.spin_line_width.setValue(1.5)
        self.combo_color.setCurrentIndex(0)

    def get_values(self):
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
            "STYLE_LINE_WIDTH": self.spin_line_width.value(),
            "STYLE_COLOR_RAW": selected_color
        }

    def _load_current_values(self):
        self.spin_gauge.setValue(MaterialConstants.GAUGE_LENGTH_MM)
        self.spin_elas_lower.setValue(MaterialConstants.ELASTIC_LOWER_RATIO)
        self.spin_elas_upper.setValue(MaterialConstants.ELASTIC_UPPER_RATIO)
        self.spin_crack_tol.setValue(MaterialConstants.CRACK_TOLERANCE_BASE)
        self.spin_ult_ratio.setValue(getattr(MaterialConstants, "ULTIMATE_STRAIN_RATIO", 0.85))
        self.spin_smooth.setValue(MaterialConstants.SMOOTH_WINDOW)
        self.spin_line_width.setValue(getattr(MaterialConstants, "STYLE_LINE_WIDTH", 1.5))

        val_col = getattr(MaterialConstants, "STYLE_COLOR_RAW", "#2c3e50")
        c_map = ["#2c3e50", "#7f8c8d", "#000000", "#c0392b", "#27ae60"]
        self.combo_color.setCurrentIndex(c_map.index(val_col) if val_col in c_map else 0)