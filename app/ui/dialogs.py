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
)
from PySide6.QtCore import Qt
from app.core.physics import MaterialConstants


class SettingsDialog(QDialog):
    """Configuration dialog.

    Important fix: OK now writes values to MaterialConstants before closing.
    The previous dialog only returned Accepted, so the UI appeared to save
    settings while the analysis configuration stayed unchanged.
    """

    COLOR_OPTIONS = [
        ("Scientific Blue (#2c3e50)", "#2c3e50"),
        ("Classic Gray (#7f8c8d)", "#7f8c8d"),
        ("Deep Black (#000000)", "#000000"),
        ("Crimson Red (#c0392b)", "#c0392b"),
        ("Emerald Green (#27ae60)", "#27ae60"),
    ]

    UNIT_OPTIONS = [
        ("Auto - infer by threshold", "auto"),
        ("Percent - 0.5 means 0.5%", "percent"),
        ("Decimal - 0.005 means 0.5%", "decimal"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration & Constitutive Manual (设置与本构说明)")
        self.resize(980, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(15)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._create_physics_tab(), "⚙️ Parameters (参数)")
        self.tabs.addTab(self._create_manual_tab(), "📖 Dictionary (释义)")
        root.addWidget(self.tabs)

        bottom = QHBoxLayout()
        self.btn_reset = QPushButton("↺ Reset Defaults")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self._reset_to_defaults)
        bottom.addWidget(self.btn_reset)
        bottom.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        bottom.addWidget(self.buttons)
        root.addLayout(bottom)

        self.setStyleSheet("""
            QDialog { background: #ffffff; }
            QGroupBox { font-weight: 700; color: #202124; border: 1px solid #dadce0; border-radius: 8px; margin-top: 12px; padding-top: 20px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; background: #fff; color: #1a73e8; }
            QDoubleSpinBox, QSpinBox, QComboBox { padding: 6px; border: 1px solid #dadce0; border-radius: 4px; background: #fff; }
            QPushButton { padding: 6px 16px; border-radius: 4px; font-weight: 600; }
        """)
        self._load_current_values()

    def _create_physics_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(18)

        grp_units = QGroupBox("1. Geometry & Units (几何与单位)")
        form_units = QFormLayout(grp_units)
        form_units.setSpacing(12)

        self.spin_gauge = self._make_double_spin(10.0, 500.0, 1.0)
        self.combo_unit = QComboBox()
        for text, _ in self.UNIT_OPTIONS:
            self.combo_unit.addItem(text)
        self.spin_strain_threshold = self._make_double_spin(0.001, 5.0, 0.01, decimals=3)

        form_units.addRow("Gauge Length L₀ (mm):", self.spin_gauge)
        form_units.addRow("Input Strain Unit:", self.combo_unit)
        form_units.addRow("Auto Percent Threshold:", self.spin_strain_threshold)
        layout.addWidget(grp_units)

        grp_lop = QGroupBox("2. Modulus & First Cracking (模量与初裂)")
        form_lop = QFormLayout(grp_lop)
        form_lop.setSpacing(12)

        self.spin_elas_lower = self._make_double_spin(0.0, 1.0, 0.05)
        self.spin_elas_upper = self._make_double_spin(0.0, 1.0, 0.05)
        self.spin_crack_tol = self._make_double_spin(0.001, 1.0, 0.005, decimals=3)
        self.spin_crack_ratio = self._make_double_spin(0.0, 0.2, 0.005, decimals=3)
        self.spin_stiffness = self._make_double_spin(0.1, 1.0, 0.01)
        self.spin_min_stress = self._make_double_spin(0.0, 0.5, 0.01)

        form_lop.addRow("Elastic Fit Lower Ratio:", self.spin_elas_lower)
        form_lop.addRow("Elastic Fit Upper Ratio:", self.spin_elas_upper)
        form_lop.addRow("Crack Tolerance Base (MPa):", self.spin_crack_tol)
        form_lop.addRow("Crack Tolerance Ratio:", self.spin_crack_ratio)
        form_lop.addRow("Stiffness Constraint:", self.spin_stiffness)
        form_lop.addRow("Min Stress Ratio:", self.spin_min_stress)
        layout.addWidget(grp_lop)

        grp_signal = QGroupBox("3. Failure & Visualization (失效与绘图)")
        form_signal = QFormLayout(grp_signal)
        form_signal.setSpacing(12)

        self.spin_ult_ratio = self._make_double_spin(0.50, 1.00, 0.01)
        self.spin_smooth = QSpinBox()
        self.spin_smooth.setRange(3, 101)
        self.spin_smooth.setSingleStep(2)
        self.spin_line_width = self._make_double_spin(0.5, 5.0, 0.5)
        self.combo_color = QComboBox()
        for text, _ in self.COLOR_OPTIONS:
            self.combo_color.addItem(text)

        form_signal.addRow("Rupture Ratio (Post-Peak):", self.spin_ult_ratio)
        form_signal.addRow("Smoothing Window (Points):", self.spin_smooth)
        form_signal.addRow("Base Line Width (px):", self.spin_line_width)
        form_signal.addRow("Default Curve Color:", self.combo_color)
        layout.addWidget(grp_signal)

        layout.addStretch()
        return widget

    def _create_manual_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        viewer = QTextBrowser()
        viewer.setOpenExternalLinks(True)
        viewer.setHtml("""
        <h2>ECC Analyzer Pro - Algorithm Dictionary</h2>
        <p><b>Strain unit is now explicit.</b> Auto mode treats values above the configured threshold as percent strain.
        For example, with threshold 0.2, input <code>0.5</code> is interpreted as <code>0.5%</code>, while
        <code>0.005</code> remains decimal strain.</p>
        <h3>Effective modulus E_eff</h3>
        <p>Linear regression between the configured lower and upper stress ratios of peak stress.</p>
        <h3>First cracking strength σ_cr</h3>
        <p>Detected only when linear deviation, tangent stiffness degradation, and minimum stress threshold are satisfied together.</p>
        <h3>Ultimate / limit strain ε_u</h3>
        <p>Post-peak limit point where stress falls below the configured ratio of peak stress after a look-ahead check.</p>
        <h3>Fracture energy G_F</h3>
        <p>Simpson integration of stress-strain response up to the limit point, multiplied by gauge length.</p>
        <h3>Compressive mode</h3>
        <p>Negative compressive stress values are converted to positive magnitudes before strength extraction.</p>
        """)
        layout.addWidget(viewer)
        return widget

    def _make_double_spin(self, min_val, max_val, step, decimals=2):
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setFixedWidth(150)
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

    def accept(self):
        values = self.get_values()
        MaterialConstants.update_config(**values)
        super().accept()
