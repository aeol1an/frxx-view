"""Print double-clicked radar values to the shell."""
from __future__ import annotations

from typing import Any


def execute(app_state, shell_output: Any, *args: str):
    """Toggle readable double-click value output for the main window."""
    if args:
        shell_output.emit(":vals does not accept arguments", 1)
        return

    window = app_state.main_window
    callback = getattr(window, "_vals_callback", None)
    if callback is not None:
        try:
            app_state.panel_double_clicked.disconnect(callback)
        except (RuntimeError, TypeError):
            pass
        window._vals_callback = None
        shell_output.emit("Double-click values disabled", 0)
        return

    def print_value(payload: dict):
        shell_output.emit(_format_payload(payload), 0)

    window._vals_callback = print_value
    app_state.panel_double_clicked.connect(print_value)
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
