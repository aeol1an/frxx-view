"""Print double-clicked moment values to the shell."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ValsSession:
    app_state: Any
    shell_output: Any
    manager: Any = None
    callback: Any = None
    marker_id: str | None = None
    scope: str = "scan"

    def print_value(self, payload: dict):
        self.shell_output.emit(_format_payload(payload), 0)
        x_center = float(payload["x_center"])
        y_center = float(payload["y_center"])
        if self.marker_id is None:
            self.marker_id = self.manager.window.plot_controller.scatter(
                [x_center],
                [y_center],
                color="black",
                s=18,
            )
        else:
            self.manager.window.plot_controller.update(
                self.marker_id,
                x=[x_center],
                y=[y_center],
            )

    def close(self, reason: str):
        try:
            self.manager.window.panel_double_clicked.disconnect(self.callback)
        except (RuntimeError, TypeError):
            pass
        if self.marker_id is not None:
            try:
                self.manager.window.plot_controller.remove(self.marker_id)
            except KeyError:
                pass
        message = (
            "Double-click values disabled after sweep change"
            if reason == "scan_changed"
            else "Double-click values disabled"
        )
        self.shell_output.emit(message, 0)


def execute(app_state, interaction_manager, shell_output: Any, *args: str):
    """Toggle readable moment double-click output for one data window."""
    if args:
        shell_output.emit(":vals does not accept arguments", 1)
        return

    if interaction_manager.stop("vals", reason="toggle"):
        return

    session = ValsSession(app_state, shell_output, interaction_manager)
    session.callback = session.print_value
    interaction_manager.window.panel_double_clicked.connect(session.callback)
    interaction_manager.start("vals", session)
    shell_output.emit("Double-click values enabled", 0)


def _format_payload(payload: dict) -> str:
    return "\n".join(
        (
            f"Panel {payload['panel_number']}",
            (
                "  click:  "
                f"x={payload['event_x']:.3f}, "
                f"y={payload['event_y']:.3f}"
            ),
            (
                "  gate:   "
                f"theta[{payload['i_theta']}]="
                f"{payload['theta_center']:.3f} deg, "
                f"range[{payload['i_r']}]="
                f"{payload['r_center']:.3f} km"
            ),
            (
                "  center: "
                f"x={payload['x_center']:.3f}, "
                f"y={payload['y_center']:.3f}"
            ),
            f"  value:  {payload['value']}",
        )
    )
