import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator, FixedLocator
from itertools import cycle
from typing import List, Dict, Optional, Any
from PySide6.QtWidgets import QInputDialog
from app.core.physics import MaterialConstants

# Try to import mplcursors safely
try:
    import mplcursors

    HAS_MPLCURSORS = True
except ImportError:
    HAS_MPLCURSORS = False

# 指定后端
matplotlib.use('QtAgg')

# --- 科研配色方案 (Scientific Palette) ---
SCI_COLORS = ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#F0E442', '#56B4E9', '#E69F00', '#333333']


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=120):
        # [Fix 1] 使用 constrained_layout 替代 tight_layout，解决布局警告
        self.fig = Figure(figsize=(width, height), dpi=dpi, constrained_layout=True)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

        self._setup_global_style()
        self._init_state()

        self.mpl_connect('button_press_event', self.on_press)
        self.mpl_connect('motion_notify_event', self.on_motion)
        self.mpl_connect('button_release_event', self.on_release)
        self.mpl_connect('pick_event', self.on_pick)

    def _init_state(self):
        self.cursors = []
        self.draggable_text = None
        self.is_dragging = False
        self.drag_start_pos = None
        self.press_pos = None
        self.current_markers = []
        self.fit_lines = []
        self.advanced_artists = []

    def _setup_global_style(self):
        plt.rcParams.update({
            'font.family': 'sans-serif',
            'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'Arial', 'Helvetica', 'DejaVu Sans'],
            'mathtext.fontset': 'stixsans',
            'axes.unicode_minus': False,
            'axes.linewidth': 1.2,
            'xtick.direction': 'in',
            'ytick.direction': 'in',
            'xtick.major.width': 1.2,
            'ytick.major.width': 1.2,
            'xtick.minor.width': 0.8,
            'ytick.minor.width': 0.8,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 9,
            'figure.dpi': 120
        })

    def clear_plot(self):
        # [Optimization] Remove cursors explicitly
        if self.cursors:
            for c in self.cursors:
                try:
                    c.remove()
                except:
                    pass
        self.cursors.clear()

        self.axes.clear()
        self._init_state()
        self.axes.grid(True, which='major', linestyle='--', alpha=0.5, color='#bdc3c7', zorder=0)
        self.axes.grid(False, which='minor')

    def set_text_visibility(self, visible: bool):
        if self.draggable_text: self.draggable_text.set_visible(visible)
        for artist in self.current_markers + self.fit_lines + self.advanced_artists:
            artist.set_visible(visible)
        self.draw()

    # =========================================================================
    # 1. 专用抗压柱状图 (Single Metric Comparison)
    # =========================================================================
    def plot_single_metric_bars(self, names: List[str], means: List[float], stds: List[float],
                                ylabel: str = "Strength (MPa)"):
        self.clear_plot()
        ax = self.axes
        if not names: return

        x = np.arange(len(names))
        bar_width = 0.6
        color_cycle = cycle(SCI_COLORS)

        bars = ax.bar(x, means, yerr=stds, width=bar_width,
                      color=[next(color_cycle) for _ in range(len(names))],
                      alpha=0.9, edgecolor='black', linewidth=1.2,
                      capsize=5, error_kw={'elinewidth': 1.5, 'ecolor': '#333'}, zorder=3)

        if len(names) > 1:
            hatch_patterns = ['//', '..', '\\\\', 'xx', '--']
            for i, bar in enumerate(bars):
                bar.set_hatch(hatch_patterns[i % len(hatch_patterns)])
                bar.set_edgecolor('black')
                bar.set_linewidth(1.0)

        ax.bar_label(bars, fmt='%.1f', padding=4, fontsize=10, fontweight='bold')

        ax.xaxis.set_major_locator(FixedLocator(x))
        ax.set_xticklabels(names, fontweight='bold', fontsize=11, rotation=30 if len(names) > 5 else 0)
        ax.set_ylabel(ylabel, fontweight='bold', fontsize=12)
        ax.set_title("Compressive Strength Comparison", fontsize=14, fontweight='bold', pad=15)

        self._apply_scientific_axis_style(ax, is_categorical=True)
        ax.set_ylim(bottom=0)
        self.draw()

    # =========================================================================
    # 2. 多参数分组柱状图 (General Statistics)
    # =========================================================================
    def plot_grouped_statistics(self, group_names: List[str], metrics_data: Dict, param_labels: List[str]):
        self.clear_plot()
        ax = self.axes
        n_groups = len(group_names)
        n_params = len(param_labels)
        if n_groups == 0 or n_params == 0: return

        x = np.arange(n_params)
        bar_width = 0.8 / n_groups
        color_cycle = cycle(SCI_COLORS)

        for i, gname in enumerate(group_names):
            if gname not in metrics_data: continue
            stats = metrics_data[gname]
            means = stats.get('means', [])
            stds = stats.get('stds', [])

            offset = (i - (n_groups - 1) / 2) * bar_width
            bar_color = next(color_cycle)

            bars = ax.bar(x + offset, means, yerr=stds, width=bar_width, label=gname,
                          color=bar_color, alpha=0.9, edgecolor='black', linewidth=1.0,
                          capsize=4, error_kw={'elinewidth': 1.2, 'ecolor': '#333'}, zorder=3)

            if n_groups > 1:
                hatch_patterns = ['//', '..', '\\\\', 'xx']
                for bar in bars:
                    bar.set_hatch(hatch_patterns[i % len(hatch_patterns)])
                    bar.set_linewidth(0)

            if n_groups <= 3:
                ax.bar_label(bars, fmt='%.1f', padding=3, fontsize=9, fontweight='bold', color=bar_color)

        ax.xaxis.set_major_locator(FixedLocator(x))
        ax.set_xticklabels(param_labels, fontweight='bold', fontsize=11)

        ax.set_ylabel("Metric Value", fontsize=11, fontweight='bold')
        ax.set_title("Statistical Comparison", fontsize=13, fontweight='bold', pad=12)

        self._apply_scientific_axis_style(ax, is_categorical=True)
        self._setup_legend(ax)
        ax.set_ylim(bottom=0)
        self.draw()

    # =========================================================================
    # 3. 曲线绘制 (Curves)
    # =========================================================================
    def plot_tensile(self, strain, stress, sample_name, results_dict=None,
                     show_raw=True, show_smooth=False, show_annotations=True, view_mode="basic"):
        self.clear_plot()
        if results_dict is None: results_dict = {}
        ax = self.axes
        if len(strain) == 0: return

        x_pct = strain * 100
        c_raw = getattr(MaterialConstants, 'STYLE_COLOR_RAW', '#2c3e50')
        lw = getattr(MaterialConstants, 'STYLE_LINE_WIDTH', 1.5)

        if len(x_pct) <= 5:
            ax.scatter(x_pct, stress, color=c_raw, s=120, marker='D', edgecolors='black', label=sample_name, zorder=3)
        else:
            stroke = [path_effects.withStroke(linewidth=lw + 2.0, foreground="white", alpha=0.8)]
            line, = ax.plot(x_pct, stress, color=c_raw, lw=lw, alpha=1.0, label=sample_name, zorder=3, rasterized=True)
            line.set_path_effects(stroke)
            self._draw_fit_line(ax, x_pct, results_dict, visible=show_annotations)
            self._draw_annotations(ax, x_pct, stress, results_dict, visible=show_annotations, view_mode=view_mode)
            if view_mode.lower() == "advanced":
                self._draw_advanced_visuals(ax, x_pct, stress, results_dict, visible=show_annotations)

        is_compressive = results_dict.get("Type") == "Compressive"
        xlabel = r"Compressive Strain, $\varepsilon$ (%)" if is_compressive else r"Tensile Strain, $\varepsilon$ (%)"
        ylabel = r"Compressive Stress, $\sigma$ (MPa)" if is_compressive else r"Tensile Stress, $\sigma$ (MPa)"

        self._setup_axes_limits(ax, x_pct, stress)
        ax.set_xlabel(xlabel, fontweight='bold', fontsize=11)
        ax.set_ylabel(ylabel, fontweight='bold', fontsize=11)

        self._apply_scientific_axis_style(ax, is_categorical=False)
        self._setup_legend(ax)
        self.draw()

    def plot_multi_tensile(self, data_list):
        self.clear_plot()
        ax = self.axes
        if not data_list: return

        n = len(data_list)
        colors = plt.cm.viridis(np.linspace(0, 0.9, n))
        color_cycle = cycle(colors)

        lines = []
        all_x = [];
        all_y = []
        current_lw = getattr(MaterialConstants, 'STYLE_LINE_WIDTH', 1.5)
        stroke = [path_effects.withStroke(linewidth=current_lw + 1.5, foreground="white", alpha=0.7)]

        for data in data_list:
            x = data.get("raw_strain", []) * 100
            y = data.get("raw_stress", [])
            if len(x) == 0: continue
            all_x.append(x);
            all_y.append(y)
            color = next(color_cycle)

            if len(x) > 3:
                line, = ax.plot(x, y, color=color, lw=current_lw, alpha=0.85, label=data['Sample ID'], zorder=3,
                                rasterized=True)
                line.set_path_effects(stroke)
                lines.append(line)
            else:
                ax.scatter(x, y, color=color, s=60, marker='o', edgecolors='white', label=data['Sample ID'], zorder=3)

        if lines: self._add_hover_cursor(lines)
        ax.set_title(f"Comparison Overlay ({n} Samples)", fontweight='bold', fontsize=12)
        if all_x: self._setup_axes_limits(ax, np.concatenate(all_x), np.concatenate(all_y))

        first_type = str(data_list[0].get("Type", ""))
        is_compressive = "Compressive" in first_type
        ax.set_xlabel(
            r"Compressive Strain, $\varepsilon$ (%)" if is_compressive else r"Tensile Strain, $\varepsilon$ (%)",
            fontweight='bold', fontsize=11)
        ax.set_ylabel(r"Compressive Stress, $\sigma$ (MPa)" if is_compressive else r"Tensile Stress, $\sigma$ (MPa)",
                      fontweight='bold', fontsize=11)

        self._apply_scientific_axis_style(ax, is_categorical=False)
        if n <= 12: self._setup_legend(ax, fontsize=8)
        self.draw()

    # =========================================================================
    # Helpers
    # =========================================================================
    def _apply_scientific_axis_style(self, ax, is_categorical=False):
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        formatter_y = ScalarFormatter(useMathText=True)
        formatter_y.set_powerlimits((-2, 3))
        ax.yaxis.set_major_formatter(formatter_y)

        if not is_categorical:
            ax.xaxis.set_minor_locator(AutoMinorLocator())
            formatter_x = ScalarFormatter(useMathText=True)
            formatter_x.set_powerlimits((-2, 3))
            ax.xaxis.set_major_formatter(formatter_x)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    def _setup_legend(self, ax, fontsize=9):
        leg = ax.legend(loc='best', frameon=True, fontsize=fontsize, fancybox=False, edgecolor='black', framealpha=0.9,
                        shadow=True)
        leg.set_draggable(True)

    def _setup_axes_limits(self, ax, x_data, y_data):
        # [Fix] Filter NaN/Inf and handle empty/zero data safely
        x_clean = x_data[np.isfinite(x_data)]
        y_clean = y_data[np.isfinite(y_data)]

        x_max = np.max(x_clean) if len(x_clean) > 0 else 0
        y_max = np.max(y_clean) if len(y_clean) > 0 else 0

        if x_max <= 1e-9: x_max = 1.0
        if y_max <= 1e-9: y_max = 1.0

        ax.set_xlim(left=-x_max * 0.02, right=x_max * 1.15)
        ax.set_ylim(bottom=-y_max * 0.02, top=y_max * 1.15)

    def _draw_fit_line(self, ax, x_pct, results_dict, visible=True):
        E_eff = results_dict.get("E_eff (GPa)", 0);
        intercept = results_dict.get("_E_intercept", 0);
        idx_cr = results_dict.get("_idx_cr", 0)
        if E_eff > 0.1 and idx_cr is not None and idx_cr < len(x_pct):
            x_fit = np.linspace(0, x_pct[idx_cr] * 1.2, 50);
            y_fit = (E_eff * 10.0) * x_fit + intercept
            line, = ax.plot(x_fit, y_fit, linestyle=(0, (5, 5)), color='#e74c3c', linewidth=1.5, label=r'$E_{eff}$ Fit',
                            alpha=0.8, zorder=2, visible=visible)
            self.fit_lines.append(line)

    def _draw_advanced_visuals(self, ax, x_pct, stress, results_dict, visible=True):
        idx_u = results_dict.get("_idx_u");
        idx_cr = results_dict.get("_idx_cr")
        if idx_u is None or idx_u >= len(x_pct): return
        poly = ax.fill_between(x_pct[:idx_u + 1], 0, stress[:idx_u + 1], color='#3498db', alpha=0.15,
                               label='Strain Energy', zorder=1, rasterized=True)
        poly.set_visible(visible);
        self.advanced_artists.append(poly)
        if idx_cr is not None and idx_cr < idx_u:
            x_s, x_e = x_pct[idx_cr], x_pct[idx_u];
            y_pos = np.max(stress[:idx_u + 1]) * 0.6
            anno = ax.annotate('', xy=(x_s, y_pos), xytext=(x_e, y_pos),
                               arrowprops=dict(arrowstyle='<->', color='#9b59b6', lw=1.8), zorder=5, visible=visible)
            txt = ax.text((x_s + x_e) / 2, y_pos * 1.08, r'$\Delta\varepsilon_{sh}$', color='#8e44ad', ha='center',
                          va='bottom', fontsize=12, fontweight='bold', visible=visible)
            self.advanced_artists.append(anno);
            self.advanced_artists.append(txt)

    def _draw_annotations(self, ax, x_pct, stress, results_dict, visible=True, view_mode="basic"):
        cv_val = results_dict.get("Plateau Stability (CV)", 0);
        cv_str = f"{cv_val:.2e}" if (0 < cv_val < 0.001) else f"{cv_val:.4f}"
        if view_mode.lower() == "advanced":
            txt = f"$\\bf{{Analysis\\ Parameters}}$\n$E_{{init}} = {results_dict.get('E_init (GPa)', 0):.2f}$ GPa\n$E_d = {results_dict.get('Strain Energy (kJ/m³)', 0):.1f}$ kJ/m$^3$\n$G_F = {results_dict.get('Fracture Energy (kJ/m²)', 0):.1f}$ kJ/m$^2$\n$\\Delta\\varepsilon_{{sh}} = {results_dict.get('Hardening Capacity (%)', 0):.2f}\\%$\n$CV_{{\\sigma}} = {cv_str}$"
        else:
            txt = f"$\\bf{{Key\\ Properties}}$\n$E_{{eff}} = {results_dict.get('E_eff (GPa)', 0):.2f}$ GPa\n$\\sigma_{{cr}} = {results_dict.get('First Crack Strength (MPa)', 0):.2f}$ MPa\n$\\sigma_{{u}} = {results_dict.get('Ultimate Stress (MPa)', 0):.2f}$ MPa\n$\\varepsilon_{{u}} = {results_dict.get('Ultimate Strain (%)', 0):.2f}\\%$"
        self.draggable_text = ax.text(0.60, 0.15, txt, transform=ax.transAxes, fontsize=10, va='bottom', ha='left',
                                      bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.95,
                                                edgecolor='#333', linewidth=0.8), picker=True, visible=visible,
                                      zorder=5)

        kp = [("_idx_peak", r'Peak ($\sigma_u$)', '*', '#27ae60', 14),
              ("_idx_cr", r'LOP ($\sigma_{cr}$)', 'o', '#e67e22', 8),
              ("_idx_u", r'Limit ($\varepsilon_u$)', 'X', '#c0392b', 10)]
        for k, l, m, c, s in kp:
            idx = results_dict.get(k)
            if idx is not None and idx < len(x_pct):
                self.current_markers.append(
                    ax.plot(x_pct[idx], stress[idx], m, color=c, markersize=s, markeredgecolor='white',
                            markeredgewidth=1.0, label=l, zorder=4, visible=visible)[0])

    def _add_hover_cursor(self, artists):
        if not artists or not HAS_MPLCURSORS: return
        try:
            cursor = mplcursors.cursor(artists, hover=True)

            @cursor.connect("add")
            def on_add(sel):
                x, y = sel.target;
                l = sel.artist.get_label()
                sel.annotation.set_text(f"{l}\nε={x:.3f}%\nσ={y:.2f}");
                sel.annotation.get_bbox_patch().set(fc="white", alpha=0.9, ec="#ccc");
                sel.annotation.arrow_patch.set(arrowstyle="-", fc="white", alpha=0.5)

            self.cursors.append(cursor)
        except:
            pass

    def _is_zoom_mode(self):
        try:
            return self.parent().toolbar.mode != ""
        except:
            return False

    def on_press(self, event):
        if event.button != 1 or self._is_zoom_mode(): return
        if event.inaxes == self.axes and self.draggable_text and self.draggable_text.contains(event)[0]:
            self.is_dragging = True;
            self.drag_start_pos = (event.x, event.y);
            self.press_pos = (event.x, event.y)
            for c in self.cursors:
                if hasattr(c, 'bg'): c.bg.set_visible(False)

    def on_motion(self, event):
        if not self.is_dragging or not event.inaxes: return
        dx = event.x - self.drag_start_pos[0];
        dy = event.y - self.drag_start_pos[1]
        bbox = self.axes.bbox;
        self.draggable_text.set_position((self.draggable_text.get_position()[0] + dx / bbox.width,
                                          self.draggable_text.get_position()[1] + dy / bbox.height))
        self.drag_start_pos = (event.x, event.y);
        self.draw_idle()

    def on_release(self, event):
        self.is_dragging = False
        for c in self.cursors:
            if hasattr(c, 'bg'): c.bg.set_visible(True)

    def on_pick(self, event):
        if event.mouseevent.button != 1 or self._is_zoom_mode(): return
        if event.artist == self.draggable_text and self.press_pos and np.hypot(event.mouseevent.x - self.press_pos[0],
                                                                               event.mouseevent.y - self.press_pos[
                                                                                   1]) < 3:
            txt, ok = QInputDialog.getMultiLineText(self, "Edit Annotation", "Text:", self.draggable_text.get_text())
            if ok: self.draggable_text.set_text(txt); self.draw()