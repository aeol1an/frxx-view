"""
Grid container managing the 4 persistent PanelFrames.

Handles layout switching (show/hide + reposition) and replot orchestration
via user-supplied factory callbacks.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import QWidget, QGridLayout, QApplication
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from frxxv.config import LAYOUTS, NUM_PANELS
from frxxv.state import AppState, PanelState
from frxxv.widgets.panel_frame import PanelFrame

# ── Factory type aliases ────────────────────────────────────────────
#
# PlotFactory signature:
#   (panel_state, scan_data, width_inches, height_inches, dpi) -> None
#   Must set panel_state.fig / .ax / .plot / .cb / .xlim / .y_center
#
# UpdateFactory signature:
#   (panel_state, scan_data) -> bool   (True = fast update succeeded)
PlotFactory   = Callable[..., None]
UpdateFactory = Callable[..., bool]


class PanelGrid(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state

        self._plot_factory:   Optional[PlotFactory]   = None
        self._update_factory: Optional[UpdateFactory] = None

        # Grid
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(4)

        # Create all panels once — they persist across layout changes
        self.panels: list[PanelFrame] = [
            PanelFrame(i, self.state, self) for i in range(NUM_PANELS)
        ]

        # Wire state signals
        self.state.layout_changed.connect(self._apply_layout)
        self.state.panel_field_changed.connect(self.replot_panel)
        self.state.scan_changed.connect(self._update_all_panels)

        # Apply whatever layout AppState was initialized with
        self._apply_layout(self.state.layout)

    # ── Public API ──────────────────────────────────────────────────

    def set_plot_factory(self, factory: PlotFactory):
        """
        Register the function that creates a figure from scratch.

        Expected to mutate the PanelState in-place:
            factory(panel_state, scan_data, width_in, height_in, dpi) -> None
        """
        self._plot_factory = factory

    def set_update_factory(self, factory: UpdateFactory):
        """
        Register an optional fast-update function (e.g. set_array).

        Expected signature:
            factory(panel_state, scan_data) -> bool
        """
        self._update_factory = factory

    def replot_panel(self, index: int):
        """Full replot of one panel via the plot factory."""
        if self._plot_factory is None:
            return
        pf = self.panels[index]
        ps = self.state.panels[index]
        dpi = self._get_display_dpi()

        self._plot_factory(ps, self.state.scan_data,
                           pf.width_inches, pf.height_inches, dpi)

        if ps.fig is not None:
            canvas = FigureCanvasQTAgg(ps.fig)
            pf.set_canvas(canvas)

    # ── Layout switching ────────────────────────────────────────────

    def _apply_layout(self, layout_key: str):
        # Pull everything out of the grid
        for panel in self.panels:
            self._grid.removeWidget(panel)
            panel.hide()

        positions = LAYOUTS.get(layout_key, LAYOUTS["2x2"])

        # Grid extent
        max_row = max(r + rs for r, _, rs, _ in positions)
        max_col = max(c + cs for _, c, _, cs in positions)

        # Equal stretch for active rows/cols, zero for inactive
        for r in range(2):
            self._grid.setRowStretch(r, 1 if r < max_row else 0)
        for c in range(2):
            self._grid.setColumnStretch(c, 1 if c < max_col else 0)

        for i, (r, c, rs, cs) in enumerate(positions):
            self._grid.addWidget(self.panels[i], r, c, rs, cs)
            self.panels[i].show()

        # Deselect if the selected panel is now hidden
        if self.state.selected is not None and self.state.selected >= len(positions):
            self.state.selected = None

    # ── Scan-changed update ─────────────────────────────────────────

    def _update_all_panels(self):
        layout_key = self.state.layout
        visible = len(LAYOUTS.get(layout_key, LAYOUTS["2x2"]))

        for i in range(visible):
            ps = self.state.panels[i]
            # Try fast path first
            if self._update_factory is not None and ps.fig is not None:
                if self._update_factory(ps, self.state.scan_data):
                    if self.panels[i].canvas is not None:
                        self.panels[i].canvas.draw_idle() #type: ignore
                    continue
            # Fall back to full replot
            self.replot_panel(i)

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _get_display_dpi() -> float:
        screen = QApplication.primaryScreen()
        if screen is not None:
            return screen.logicalDotsPerInch()
        return 100.0