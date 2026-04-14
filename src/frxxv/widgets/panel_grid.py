"""
Grid container managing the 4 persistent PanelFrames.

Handles layout switching (show/hide + reposition) and replot orchestration
via user-supplied factory callbacks.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import QWidget, QGridLayout, QApplication
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from frxxv.config import LAYOUTS, NUM_PANELS, MIN_PANEL_HEIGHT_INCHES, MIN_PANEL_WIDTH_INCHES
from frxxv.state import AppState, PanelState
from frxxv.widgets.panel_frame import PanelFrame

# ── Factory type aliases ────────────────────────────────────────────
#
# PlotFactory signature:
#   (panel_state, scan_data, width_inches, height_inches, dpi) -> None
#   Must set panel_state.fig / .ax / .plot / .cb / .xlim / .ylim
#
# UpdateFactory signature:
#   (panel_state, scan_data) -> bool   (True = fast update succeeded)
PlotFactory   = Callable[..., None]
UpdateFactory = Callable[..., bool]


class PanelGrid(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state

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

    def replot_panel(self, index: int):
        pf = self.panels[index]
        pf.replot()

    # ── Layout switching ────────────────────────────────────────────

    def _apply_layout(self, layout_key: str):
        # Capture current panel size BEFORE layout change
        panel_size = self.panels[0].size()

        for panel in self.panels:
            self._grid.removeWidget(panel)
            panel.hide()

        positions = LAYOUTS.get(layout_key, LAYOUTS["2x2"])

        max_row = max(r + rs for r, _, rs, _ in positions)
        max_col = max(c + cs for _, c, _, cs in positions)

        for r in range(2):
            self._grid.setRowStretch(r, 1 if r < max_row else 0)
        for c in range(2):
            self._grid.setColumnStretch(c, 1 if c < max_col else 0)

        # Lock all panels to their old size
        for panel in self.panels:
            panel.setFixedSize(panel_size)

        for i, (r, c, rs, cs) in enumerate(positions):
            self._grid.addWidget(self.panels[i], r, c, rs, cs)
            self.panels[i].show()

        if self.state.selected is not None and self.state.selected >= len(positions):
            self.state.selected = None

        # Let the window shrink/grow to fit the locked panels
        self.window().adjustSize()

        # Now unlock so manual resize works again
        QWIDGETSIZE_MAX = 16777215
        for panel in self.panels:
            panel.setMinimumSize(
                int(MIN_PANEL_WIDTH_INCHES * panel.dpi_x),
                int(MIN_PANEL_HEIGHT_INCHES * panel.dpi_y),
            )
            panel.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)

    # ── Scan-changed update ─────────────────────────────────────────

    def _update_all_panels(self):
        layout_key = self.state.layout
        visible = len(LAYOUTS.get(layout_key, LAYOUTS["2x2"]))

        for i in range(visible):
            panel = self.panels[i]
            ps = self.state.panels[i]
            # Try fast path first
            if self._update_factory is not None and ps.fig is not None:
                if self._update_factory(ps, self.state.scan_data):
                    if self.panels[i].canvas is not None:
                        self.panels[i].canvas.draw_idle() #type: ignore
                    continue
            # Fall back to full replot
            panel.replot()
