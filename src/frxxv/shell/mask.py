"""Toggle visualization of the combined interaction mask."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class MaskSession:
    app_state: Any
    shell_output: Any
    manager: Any
    field_callback: Any = None
    scope: str = "scan"

    def update(self, combined_mask):
        """Apply the current aggregate mask to every panel's data artist."""
        for panel_index in range(len(self.manager.window.state.panels)):
            self._apply_panel(panel_index, combined_mask)

    def reapply_panel(self, panel_index: int):
        """Reapply masking after a product change replaces a panel plot."""
        combined_mask = self.manager.masks.mask
        if combined_mask is not None:
            self._apply_panel(panel_index, combined_mask)

    def _apply_panel(self, panel_index: int, combined_mask):
        panel_state = self.manager.window.state.panels[panel_index]
        if panel_state.plot is None or panel_state.data is None:
            return

        hidden = np.asarray(combined_mask) == 0
        original_hidden = np.ma.getmaskarray(panel_state.data)
        display_data = np.ma.array(
            np.ma.getdata(panel_state.data),
            mask=np.logical_or(original_hidden, hidden),
            copy=True,
        )
        panel_state.plot.set_array(display_data)
        self._draw_panel(panel_index)

    def close(self, reason: str):
        try:
            self.manager.masks.changed.disconnect(self.update)
        except (RuntimeError, TypeError):
            pass
        try:
            self.manager.window.state.panel_field_changed.disconnect(
                self.field_callback
            )
        except (RuntimeError, TypeError):
            pass

        for panel_index, panel_state in enumerate(
            self.manager.window.state.panels
        ):
            if panel_state.plot is None or panel_state.data is None:
                continue
            panel_state.plot.set_array(panel_state.data)
            self._draw_panel(panel_index)

        message = (
            "Mask display disabled after sweep change"
            if reason == "scan_changed"
            else "Mask display disabled"
        )
        self.shell_output.emit(message, 0)

    def _draw_panel(self, panel_index: int):
        panel_frame = self.manager.window.panel_grid.panels[panel_index]
        if panel_frame.canvas is not None:
            panel_frame.canvas.draw_idle()


def execute(app_state, interaction_manager, shell_output: Any, *args: str):
    """Toggle the combined mask display on every panel."""
    if args:
        shell_output.emit(":mask does not accept arguments", 1)
        return

    manager = interaction_manager
    if manager.stop("mask", reason="toggle"):
        return

    combined_mask = manager.masks.mask
    if combined_mask is None:
        shell_output.emit("No panel data available for mask display", 1)
        return

    session = MaskSession(app_state, shell_output, manager)
    session.field_callback = session.reapply_panel
    manager.masks.changed.connect(session.update)
    manager.window.state.panel_field_changed.connect(session.field_callback)
    manager.start("mask", session)
    session.update(combined_mask)
    shell_output.emit("Mask display enabled", 0)
