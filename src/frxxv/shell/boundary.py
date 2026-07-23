"""Interactive, persistent PPI boundary drawing."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose
from typing import Any

import numpy as np
from matplotlib.path import Path
from numpy.typing import NDArray


Point = tuple[float, float]


@dataclass
class BoundarySession:
    app_state: Any = None
    shell_output: Any = None
    manager: Any = None
    points: list[Point] = field(default_factory=list)
    gatewidths: list[float] = field(default_factory=list)
    overlay_id: str | None = None
    closed: bool = False
    callback: Any = None
    scope: str = "scan"

    def close(self, reason: str):
        try:
            self.app_state.panel_double_clicked.disconnect(self.callback)
        except (RuntimeError, TypeError):
            pass

        if self.overlay_id is not None:
            try:
                self.app_state.plot_controller.remove(self.overlay_id)
            except KeyError:
                pass

        self.manager.mask = None

        # ── DEBUG: restore Panel 1 after mask visualization ─────────
        panel_state = self.app_state.panels[1]
        panel_frame = self.app_state.main_window.panel_grid.panels[1]
        if panel_state.plot is not None and panel_state.data is not None:
            panel_state.plot.set_array(panel_state.data)
            if panel_frame.canvas is not None:
                panel_frame.canvas.draw_idle()
        # ── END DEBUG: restore Panel 1 after mask visualization ─────

        message = (
            "Boundary disabled after sweep change"
            if reason == "scan_changed"
            else "Boundary disabled and cleared"
        )
        self.shell_output.emit(message, 0)


def execute(app_state, shell_output: Any, *args: str):
    """Toggle interactive boundary drawing."""
    if args:
        shell_output.emit(":bnd does not accept arguments", 1)
        return

    manager = app_state.main_window.interactions
    if manager.stop("boundary", reason="toggle"):
        return

    manager.mask = None
    session = BoundarySession(app_state, shell_output, manager)

    def add_boundary_point(payload: dict):
        _handle_double_click(app_state, shell_output, session, payload)

    session.callback = add_boundary_point
    app_state.panel_double_clicked.connect(add_boundary_point)
    manager.start("boundary", session)
    shell_output.emit(
        "Boundary enabled: double-click to add points; "
        "Shift+double-click to close",
        0,
    )

def _handle_double_click(
    app_state,
    shell_output: Any,
    session: BoundarySession,
    payload: dict,
):
    if session.closed or payload.get("button") != 1:
        return

    modifiers = {str(value).lower() for value in payload.get("modifiers", ())}
    key = str(payload.get("key") or "").lower()

    if modifiers == {"shift"} and key in ("", "shift"):
        _close_boundary(
            app_state,
            shell_output,
            session,
            int(payload["panel_number"]),
        )
        return
    if modifiers or key:
        return

    point = (float(payload["x_center"]), float(payload["y_center"]))
    if any(_same_point(point, existing) for existing in session.points):
        shell_output.emit("Boundary point duplicates an existing point", 1)
        return

    if _new_segment_intersects(session.points, point):
        shell_output.emit("Boundary segment would intersect itself", 1)
        return

    session.points.append(point)
    session.gatewidths.append(float(payload["theta_gatewidth"]))
    _render(app_state, session)


def _close_boundary(
    app_state,
    shell_output: Any,
    session: BoundarySession,
    panel_number: int,
):
    if len(session.points) < 3:
        shell_output.emit("Boundary needs at least three points to close", 1)
        return
    if _closing_segment_intersects(session.points):
        shell_output.emit("Closing segment would intersect the boundary", 1)
        return
    signed_area = _signed_area(session.points)
    if isclose(signed_area, 0.0, abs_tol=1e-12):
        shell_output.emit("Boundary has zero area and cannot be closed", 1)
        return

    grid = app_state.panels[panel_number].grid
    if grid is None:
        shell_output.emit("Panel has no gate-center grid", 1)
        return

    positive_gatewidths = [
        width for width in session.gatewidths if np.isfinite(width) and width > 0
    ]
    if not positive_gatewidths:
        shell_output.emit("Could not determine an angular gate width", 1)
        return

    inclusive_radius = min(positive_gatewidths)
    session.manager.mask = _build_mask(
        session.points,
        grid,
        inclusive_radius,
        signed_area,
    )

    session.closed = True
    _render(app_state, session)
    shell_output.emit("Boundary closed", 0)

    # ── DEBUG: visualize boundary mask on Panel 1 ───────────────────
    panel_state = app_state.panels[1]
    panel_frame = app_state.main_window.panel_grid.panels[1]
    if panel_state.plot is not None and panel_state.data is not None:
        masked_data = np.ma.array(
            panel_state.data,
            mask=session.manager.mask,
            copy=True,
        )
        panel_state.plot.set_array(masked_data)
        if panel_frame.canvas is not None:
            panel_frame.canvas.draw_idle()
    # ── END DEBUG: visualize boundary mask on Panel 1 ───────────────


def _render(app_state, session: BoundarySession):
    points = session.points + ([session.points[0]] if session.closed else [])
    x = [point[0] for point in points]
    y = [point[1] for point in points]
    controller = app_state.plot_controller

    if session.overlay_id is None:
        session.overlay_id = controller.plot(
            x,
            y,
            color="red",
            marker="o",
            linewidth=1.5,
            zorder=20,
        )
    else:
        controller.update(session.overlay_id, x=x, y=y)


def _new_segment_intersects(points: list[Point], point: Point) -> bool:
    if len(points) < 2:
        return False
    start = points[-1]
    return any(
        _segments_intersect(points[index], points[index + 1], start, point)
        for index in range(len(points) - 2)
    )


def _closing_segment_intersects(points: list[Point]) -> bool:
    start, end = points[-1], points[0]
    return any(
        _segments_intersect(points[index], points[index + 1], start, end)
        for index in range(1, len(points) - 2)
    )


def _segments_intersect(p1: Point, q1: Point, p2: Point, q2: Point) -> bool:
    o1 = _orientation(p1, q1, p2)
    o2 = _orientation(p1, q1, q2)
    o3 = _orientation(p2, q2, p1)
    o4 = _orientation(p2, q2, q1)

    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and _on_segment(p1, p2, q1))
        or (o2 == 0 and _on_segment(p1, q2, q1))
        or (o3 == 0 and _on_segment(p2, p1, q2))
        or (o4 == 0 and _on_segment(p2, q1, q2))
    )


def _orientation(p: Point, q: Point, r: Point) -> int:
    value = (q[1] - p[1]) * (r[0] - q[0]) - (
        (q[0] - p[0]) * (r[1] - q[1])
    )
    if isclose(value, 0.0, abs_tol=1e-12):
        return 0
    return 1 if value > 0 else 2


def _on_segment(p: Point, q: Point, r: Point) -> bool:
    return (
        min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
        and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
    )


def _same_point(p: Point, q: Point) -> bool:
    return isclose(p[0], q[0]) and isclose(p[1], q[1])


def _signed_area(points: list[Point]) -> float:
    return 0.5 * sum(
        point[0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * point[1]
        for index, point in enumerate(points)
    )


def _build_mask(
    points: list[Point],
    grid: tuple[NDArray, NDArray],
    inclusive_radius: float,
    signed_area: float | None = None,
) -> NDArray[np.bool_]:
    """Return an inclusive gate-center mask in ``(theta, range)`` order."""
    vertices = np.asarray(points, dtype=float)
    area = _signed_area(points) if signed_area is None else signed_area

    # Normalize clockwise input to counterclockwise. This makes the positive
    # containment radius expand toward the same side of every directed edge.
    if area < 0:
        vertices = vertices[::-1]

    xx, yy = grid
    if xx.shape != yy.shape:
        raise ValueError("Boundary grid x and y arrays must have matching shapes")

    centers = np.column_stack((xx.ravel(), yy.ravel()))
    inside = Path(vertices).contains_points(
        centers,
        radius=inclusive_radius,
    )
    return inside.reshape(xx.shape)
