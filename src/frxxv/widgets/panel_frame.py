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
from matplotlib.backends.backend_qt import NavigationToolbar2QT

from typing import Callable, Optional

PlotFactory   = Callable[..., None]
UpdateFactory = Callable[..., bool]

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
from frxxv.controllers.panel_lims_controller import PanelLimsController


class PanelFrame(QFrame):
    def __init__(self, index: int, state: AppState, lims: PanelLimsController, parent=None):
        super().__init__(parent)
        self.index = index
        self.state = state
        self.lims = lims
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
        self.dpi_x = max(self.logicalDpiX()*self.devicePixelRatio(), 72)
        self.dpi_y = max(self.logicalDpiY()*self.devicePixelRatio(), 72)
        self.setMinimumSize(
            int(MIN_PANEL_WIDTH_INCHES * self.dpi_x),
            int(MIN_PANEL_HEIGHT_INCHES * self.dpi_y),
        )

        self._plot_factory:   Optional[PlotFactory]   = None
        self._update_factory: Optional[UpdateFactory] = None

        # Debounce timer for resize-relim
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._on_resize)


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

    # ── Plot Factory ────────────────────────────────────────────────

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

    # ── Event filter, handle events ─────────────────────────────────   

    def eventFilter(self, obj, event):
        """Catch right-clicks on the hosted canvas for selection."""
        if obj is self.canvas:
            handler = {
                QEvent.Type.MouseButtonPress: self._handle_mouse_press,
                # QEvent.Type.Wheel: self._handle_wheel,
                # QEvent.Type.NativeGesture: self._handle_gesture,
            }.get(event.type())
            
            if handler:
                return handler(event)
    
        return super().eventFilter(obj, event)

    # Right click selection - qt
    def _handle_mouse_press(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.state.selected = self.index
        return False
    
    # Zoom - mpl
    def _handle_zoom(self, event):
        if self.canvas is None:
            return
        ax = event.inaxes
        if ax is None:
            return
        scale = 0.9 if event.button == 'up' else 1.1
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        xdata, ydata = event.xdata, event.ydata
        ax.set_xlim([xdata - (xdata - xlim[0]) * scale, xdata + (xlim[1] - xdata) * scale])
        ax.set_ylim([ydata - (ydata - ylim[0]) * scale, ydata + (ylim[1] - ydata) * scale])
        self.canvas.draw_idle()

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

    # ── Replot self  ────────────────────────────────────────────────

    def replot(self):
        if self._plot_factory is None:
            return
        ps = self.state.panels[self.index]
        dpi = self.display_dpi

        self._plot_factory(ps, self.state.scan_data,
                            self.width_inches, self.height_inches, dpi)
        
        if ps.fig is not None:
            canvas = FigureCanvasQTAgg(ps.fig)
            self.set_canvas(canvas)

        if self.canvas is None:
            return

        ps.w = self.canvas.width()
        ps.h = self.canvas.height()

        self.canvas.mpl_connect('scroll_event', self._handle_zoom)

        toolbar = NavigationToolbar2QT(self.canvas, self)
        toolbar.hide()
        toolbar.pan()

        self.lims.register_axes(self.canvas, ps.ax)
        ps.ax.callbacks.connect('xlim_changed', self.on_xlim_change)
        ps.ax.callbacks.connect('ylim_changed', self.on_ylim_change)
        ps.ax.set_aspect("equal")


    # ── Resize → relim (no replot) ──────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.index != 0:
            return
        self._resize_timer.start()

    def _on_resize(self):
        if self.canvas is None:
            return
        ps = self.state.panels[self.index]
        if ps.ax is None or ps.xlim is None or ps.ylim is None or ps.w is None or ps.h is None:
            return

        new_w = self.canvas.width()
        new_h = self.canvas.height()
        if new_w <= 0 or new_h <= 0:
            return
        
        old_w = ps.w
        old_h = ps.h

        old_dx = (ps.xlim[1] - ps.xlim[0])
        old_dy = (ps.ylim[1] - ps.ylim[0])

        new_dx = old_dx * (new_w/old_w)
        new_dy = old_dy * (new_h/old_h)

        x_center = ps.xlim[0] + old_dx/2
        y_center = ps.ylim[0] + old_dy/2

        new_xlim = (x_center - new_dx/2, x_center + new_dx/2)
        new_ylim = (y_center - new_dy/2, y_center + new_dy/2)

        ps.ax.set_xlim(new_xlim)
        ps.ax.set_ylim(new_ylim)

        ps.w = new_w
        ps.h = new_h
        ps.xlim = new_xlim
        ps.ylim = new_ylim

        self.canvas.draw_idle()

    def on_xlim_change(self, ax):
        self.state.panels[self.index].xlim = ax.get_xlim()

    def on_ylim_change(self, ax):
        self.state.panels[self.index].ylim = ax.get_ylim()

    # ── Geometry helpers (inches) ───────────────────────────────────

    @property
    def width_inches(self) -> float:
        return self.width() / max(self.logicalDpiX()*self.devicePixelRatio() , 72)

    @property
    def height_inches(self) -> float:
        return self.height() / max(self.logicalDpiY()*self.devicePixelRatio(), 72)
    
    @property
    def display_dpi(self) -> float:
        return max(self.logicalDpiX()*self.devicePixelRatio() , 72)