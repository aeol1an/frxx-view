"""Velocity dealiasing commands and algorithms."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray


DealiasAlgorithm = Callable[[Any, Any, Any, int], NDArray]


def forced_unfolding(
    velocity,
    nyquist_velocity,
    selection_mask,
    fold_count: int,
) -> NDArray:
    """Wrap selected velocities around ``fold_count * Va``."""
    velocity = np.ma.asanyarray(velocity)
    if velocity.ndim < 1:
        raise ValueError("Velocity field must have at least one dimension")

    selected = np.asarray(selection_mask) > 0
    if selected.shape != velocity.shape:
        raise ValueError("Selection mask does not match the velocity field shape")
    if not np.any(selected):
        raise ValueError("No pixels are selected")

    try:
        nyquist = np.asarray(nyquist_velocity, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("Nyquist velocity must be numeric") from error

    if nyquist.ndim == 0 or nyquist.size == 1:
        nyquist = np.asarray(float(nyquist.reshape(-1)[0]))
    elif nyquist.ndim == 1 and nyquist.size == velocity.shape[0]:
        nyquist = nyquist.reshape(
            (velocity.shape[0],) + (1,) * (velocity.ndim - 1)
        )
    else:
        raise ValueError(
            "Nyquist velocity must be scalar or contain one value per ray"
        )

    if np.any(~np.isfinite(nyquist)) or np.any(nyquist <= 0):
        raise ValueError("Nyquist velocity must be finite and positive")

    period = 2.0 * nyquist
    lower = (fold_count - 1) * nyquist
    upper = (fold_count + 1) * nyquist
    values = np.ma.getdata(velocity)

    # Per-ray Nyquist arrays have shape (rays, 1). Broadcast them once so
    # Boolean indexing below addresses the same (ray, gate) geometry as data.
    period = np.broadcast_to(period, velocity.shape)
    lower = np.broadcast_to(lower, velocity.shape)
    upper = np.broadcast_to(upper, velocity.shape)

    # Masked and non-finite gates remain untouched even when selected.
    eligible = (
        selected
        & ~np.ma.getmaskarray(velocity)
        & np.isfinite(values)
    )
    below_interval = eligible & (values < lower)
    above_interval = eligible & (values > upper)

    # Each shift is one full aliasing period (2 * Va). Calculate shifts only
    # for selected gates outside the requested interval; gates already inside
    # it, and all unselected gates, retain their original values.
    shifts = np.zeros(velocity.shape, dtype=float)
    shifts[below_interval] = np.ceil(
        (lower[below_interval] - values[below_interval])
        / period[below_interval]
    )
    shifts[above_interval] = np.floor(
        (upper[above_interval] - values[above_interval])
        / period[above_interval]
    )

    corrected = np.ma.array(velocity, copy=True)
    changed = below_interval | above_interval
    corrected.data[changed] = (
        values[changed] + period[changed] * shifts[changed]
    )
    return corrected


COMMANDS: dict[str, DealiasAlgorithm] = {
    "fu": forced_unfolding,
    "forced_unfolding": forced_unfolding,
}


def execute(
    app_state,
    interaction_manager,
    shell_output: Any,
    action: str,
    *args: str,
):
    """Run a dealiasing algorithm on the selected panel's velocity field."""
    if len(args) != 1:
        shell_output.emit(f":{action} requires one integer fold count", 1)
        return
    try:
        fold_count = int(args[0])
    except ValueError:
        shell_output.emit(f":{action} fold count must be an integer", 1)
        return

    window = interaction_manager.window
    panel_index = app_state.selected
    if panel_index is None:
        shell_output.emit(f":{action} requires a selected panel", 1)
        return

    panel = app_state.panels[panel_index]
    resolved = window.product_manager.resolve(panel.product)
    if resolved is None:
        shell_output.emit("The selected panel product cannot be resolved", 1)
        return

    ingestible = app_state.scan_data
    if ingestible is None:
        shell_output.emit("No file is currently loaded", 1)
        return

    combined_mask = interaction_manager.masks.mask
    if combined_mask is None:
        shell_output.emit("No selection mask is available", 1)
        return
    try:
        corrected = COMMANDS[action](
            resolved.data,
            ingestible.va,
            combined_mask,
            fold_count,
        )
    except (KeyError, LookupError, TypeError, ValueError) as error:
        shell_output.emit(str(error), 1)
        return

    window.edit_manager.record_edit(resolved.raw_field, corrected)
    for index, panel_state in enumerate(app_state.panels):
        if panel_state.product is not None:
            app_state.panel_field_changed.emit(index)
