"""
Individual panel: a rounded-border frame hosting a FigureCanvasQTAgg.

Responsibilities:
  • selection highlight (right-click)
  • debounced axes relim on resize (no full replot)
  • canvas lifecycle (swap on field change)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtWidgets import QFrame, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from frxxv.config import (
    BORDER_COLOR_SELECTED,
    BORDER_COLOR_UNSELECTED,
    BORDER_WIDTH_PX,
    BORDER_RADIUS_PX,
    MIN_PANEL_WIDTH_INCHES,
    MIN_PANEL_HEIGHT_INCHES,
    RESIZE_DEBOUNCE_MS,
)
from frxxv.state import AppState


class PanelFrame(QFrame):
    def __init__(self, index: int, state: AppState, parent=None):
        super().__init__(parent)
        self.index = index
        self.state = state
        self.canvas: FigureCanvasQTAgg | None = None

        # Object name for scoped stylesheet selector
        self._obj_name = f"panel_{index}"
        self.setObjectName(self._obj_name)

        # Inner layout — margins keep the rounded border corners visible
        self._inner_layout = QVBoxLayout(self)
        margin = BORDER_WIDTH_PX + 1
        self._inner_layout.setContentsMargins(margin, margin, margin, margin)
        self._inner_layout.setSpacing(0)

        # Minimum size derived from config (in pixels at current logical DPI)
        dpi_x = max(self.logicalDpiX(), 72)
        dpi_y = max(self.logicalDpiY(), 72)
        self.setMinimumSize(
            int(MIN_PANEL_WIDTH_INCHES * dpi_x),
            int(MIN_PANEL_HEIGHT_INCHES * dpi_y),
        )

        # Debounce timer for resize-relim
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._on_debounced_resize)

        # React to selection changes
        self.state.selection_changed.connect(self._update_border)
        self._update_border()

    # ── Border styling ──────────────────────────────────────────────

    def _update_border(self, _selected=None):
        is_sel = (self.state.selected == self.index)
        color = BORDER_COLOR_SELECTED if is_sel else BORDER_COLOR_UNSELECTED
        self.setStyleSheet(
            f"QFrame#{self._obj_name} {{"
            f"  border: {BORDER_WIDTH_PX}px solid {color};"
            f"  border-radius: {BORDER_RADIUS_PX}px;"
            f"}}"
        )

    # ── Selection via right-click ───────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.state.selected = self.index
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        """Catch right-clicks on the hosted canvas for selection."""
        if obj is self.canvas and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.RightButton:
                self.state.selected = self.index
                # Don't consume — MPL can still see it if needed
        return super().eventFilter(obj, event)

    # ── Canvas lifecycle ────────────────────────────────────────────

    def set_canvas(self, new_canvas: FigureCanvasQTAgg):
        """Replace the current canvas (full replot path)."""
        if self.canvas is not None:
            self.canvas.removeEventFilter(self)
            self._inner_layout.removeWidget(self.canvas)
            self.canvas.close()
            self.canvas.setParent(None)
            self.canvas.deleteLater()

        self.canvas = new_canvas
        self._inner_layout.addWidget(new_canvas)
        new_canvas.installEventFilter(self)

    # ── Resize → relim (no replot) ──────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def _on_debounced_resize(self):
        if self.canvas is None:
            return
        ps = self.state.panels[self.index]
        if ps.ax is None or ps.xlim is None or ps.y_center is None:
            return

        w = self.canvas.width()
        h = self.canvas.height()
        if w <= 0 or h <= 0:
            return

        x_extent = ps.xlim[1] - ps.xlim[0]
        y_extent = x_extent * (h / w)
        ps.ax.set_xlim(ps.xlim)
        ps.ax.set_ylim(
            ps.y_center - y_extent / 2,
            ps.y_center + y_extent / 2,
        )
        self.canvas.draw_idle()

    # ── Geometry helpers (inches) ───────────────────────────────────

    @property
    def width_inches(self) -> float:
        return self.width() / max(self.logicalDpiX(), 72)

    @property
    def height_inches(self) -> float:
        return self.height() / max(self.logicalDpiY(), 72)