"""Basic window-scoped product editing commands."""
from __future__ import annotations

from typing import Any

import numpy as np


def execute(
    app_state,
    interaction_manager,
    shell_output: Any,
    action: str,
    *args: str,
):
    """Dispatch a basic edit command."""
    if action == "copy":
        _copy(interaction_manager, shell_output, args)
    elif action == "set":
        _set(interaction_manager, shell_output, args)
    elif action == "del":
        _delete(interaction_manager, shell_output, args)
    else:
        _move_history(interaction_manager, shell_output, action, args)


def _copy(interaction_manager, shell_output: Any, args):
    if len(args) != 2:
        shell_output.emit(":copy requires SOURCE and DESTINATION products", 1)
        return
    source, destination = args
    window = interaction_manager.window
    resolved = window.product_manager.full_product(source)
    if resolved is None:
        shell_output.emit(f"Product {source!r} is unavailable", 1)
        return

    _source_name, product = resolved
    window.edit_manager.record_new_product(destination, product)
    _replot_products(window)


def _set(interaction_manager, shell_output: Any, args):
    if len(args) != 1:
        shell_output.emit(":set requires one floating-point value", 1)
        return
    try:
        value = float(args[0])
    except ValueError:
        shell_output.emit(":set value must be a floating-point number", 1)
        return

    window = interaction_manager.window
    panel = _selected_panel(window, shell_output, ":set")
    if panel is None:
        return
    resolved = window.product_manager.resolve(panel.product)
    if resolved is None:
        shell_output.emit("The selected panel product cannot be resolved", 1)
        return

    combined_mask = interaction_manager.masks.mask
    if combined_mask is None:
        shell_output.emit("No selection mask is available", 1)
        return
    selected = np.asarray(combined_mask) > 0
    if not np.any(selected):
        shell_output.emit("No pixels are selected", 1)
        return
    if selected.shape != np.shape(resolved.data):
        shell_output.emit("Selection mask does not match the product shape", 1)
        return

    replacement = np.ma.array(resolved.data, copy=True)
    replacement[selected] = value
    window.edit_manager.record_edit(resolved.raw_field, replacement)
    _replot_products(window)


def _delete(interaction_manager, shell_output: Any, args):
    if len(args) != 1:
        shell_output.emit(":del requires one product name", 1)
        return
    window = interaction_manager.window
    resolved = window.product_manager.resolve_raw(args[0])
    if resolved is None:
        shell_output.emit(f"Product {args[0]!r} is unavailable", 1)
        return
    raw_field, _data = resolved
    window.edit_manager.record_deletion(raw_field)
    _replot_products(window)


def _move_history(interaction_manager, shell_output: Any, action: str, args):
    if len(args) > 1:
        shell_output.emit(f":{action} accepts at most one product name", 1)
        return
    window = interaction_manager.window
    if args:
        requested = args[0]
        product = next(
            (
                name
                for name in window.edit_manager.product_names()
                if name.casefold() == requested.casefold()
            ),
            requested,
        )
    else:
        panel = _selected_panel(window, shell_output, f":{action}")
        if panel is None:
            return
        if panel.product is None:
            shell_output.emit("The selected panel has no product", 1)
            return
        product = panel.product.raw_field

    moved = (
        window.edit_manager.undo(product)
        if action == "undo"
        else window.edit_manager.redo(product)
    )
    if not moved:
        shell_output.emit(f"Nothing to {action} for product {product!r}", 1)
        return
    _replot_products(window)


def _selected_panel(window, shell_output: Any, command: str):
    panel_index = window.state.selected
    if panel_index is None:
        shell_output.emit(f"{command} requires a selected panel", 1)
        return None
    return window.state.panels[panel_index]


def _replot_products(window):
    for panel_index, panel in enumerate(window.state.panels):
        if panel.product is not None:
            window.state.panel_field_changed.emit(panel_index)
