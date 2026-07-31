"""Print double-clicked moment values to the shell."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


EARTH_RADIUS_METERS = 6_378_000.0


@dataclass
class ValsSession:
    app_state: Any
    shell_output: Any
    manager: Any = None
    callback: Any = None
    marker_id: str | None = None
    scope: str = "window"

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
        self.shell_output.emit("Double-click values disabled", 0)


@dataclass
class CoordsSession:
    app_state: Any
    shell_output: Any
    manager: Any = None
    callback: Any = None
    scope: str = "window"

    def print_coords(self, payload: dict):
        ingestible = self.app_state.scan_data
        if ingestible is None:
            self.shell_output.emit("No file is currently loaded", 1)
            return
        try:
            latitude, longitude = coordinates_at_offset(
                ingestible.latitude,
                ingestible.longitude,
                east_meters=float(payload["x_center"]) * 1000.0,
                north_meters=float(payload["y_center"]) * 1000.0,
            )
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            self.shell_output.emit(str(error), 1)
            return
        self.shell_output.emit(
            f"lat, lon = {latitude:.6f}, {longitude:.6f}",
            0,
        )

    def close(self, reason: str):
        try:
            self.manager.window.panel_double_clicked.disconnect(self.callback)
        except (RuntimeError, TypeError):
            pass
        self.shell_output.emit("Double-click coordinates disabled", 0)


@dataclass
class RayTimeSession:
    app_state: Any
    shell_output: Any
    manager: Any = None
    callback: Any = None
    scope: str = "window"

    def print_ray_time(self, payload: dict):
        ingestible = self.app_state.scan_data
        if ingestible is None:
            self.shell_output.emit("No file is currently loaded", 1)
            return
        try:
            ray_index = int(payload["i_theta"])
            time_string = ingestible.constructTimeStr(ray_index)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
            self.shell_output.emit(str(error), 1)
            return
        self.shell_output.emit(f"ray_time = {time_string!r}", 0)

    def close(self, reason: str):
        try:
            self.manager.window.panel_double_clicked.disconnect(self.callback)
        except (RuntimeError, TypeError):
            pass
        self.shell_output.emit("Double-click ray times disabled", 0)


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


def execute_coords(
    app_state,
    interaction_manager,
    shell_output: Any,
    *args: str,
):
    """Toggle snapped gate latitude/longitude output."""
    if args:
        shell_output.emit(":coords does not accept arguments", 1)
        return

    if interaction_manager.stop("coords", reason="toggle"):
        return

    session = CoordsSession(app_state, shell_output, interaction_manager)
    session.callback = session.print_coords
    interaction_manager.window.panel_double_clicked.connect(session.callback)
    interaction_manager.start("coords", session)
    shell_output.emit("Double-click coordinates enabled", 0)


def execute_raytime(
    app_state,
    interaction_manager,
    shell_output: Any,
    *args: str,
):
    """Toggle snapped ray timestamp output."""
    if args:
        shell_output.emit(":raytime does not accept arguments", 1)
        return

    if interaction_manager.stop("raytime", reason="toggle"):
        return

    session = RayTimeSession(app_state, shell_output, interaction_manager)
    session.callback = session.print_ray_time
    interaction_manager.window.panel_double_clicked.connect(session.callback)
    interaction_manager.start("raytime", session)
    shell_output.emit("Double-click ray times enabled", 0)


def coordinates_at_offset(
    start_latitude: float,
    start_longitude: float,
    east_meters: float,
    north_meters: float,
) -> tuple[float, float]:
    """Convert local east/north offsets to latitude and longitude."""
    latitude = start_latitude + np.degrees(
        north_meters / EARTH_RADIUS_METERS
    )
    mean_latitude = np.radians((start_latitude + latitude) / 2.0)
    longitude_scale = EARTH_RADIUS_METERS * np.cos(mean_latitude)
    if np.isclose(longitude_scale, 0.0):
        raise ValueError("Longitude is undefined at the geographic poles")
    longitude = start_longitude + np.degrees(east_meters / longitude_scale)
    longitude = (longitude + 180.0) % 360.0 - 180.0
    return float(latitude), float(longitude)


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
