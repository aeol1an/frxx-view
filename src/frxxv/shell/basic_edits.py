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
    elif action == "edits":
        _show_edits(interaction_manager, shell_output, args)
    elif action == "rmedits":
        _remove_edits(interaction_manager, shell_output, args)
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


def _show_edits(interaction_manager, shell_output: Any, args):
    if args:
        shell_output.emit(":edits does not accept arguments", 1)
        return

    window = interaction_manager.window
    ingestible = window.state.scan_data
    if ingestible is None:
        shell_output.emit("No file is currently loaded", 1)
        return

    edit_history = window.edit_manager.edit_history
    sweep_edits = (
        {} if edit_history is None else edit_history[ingestible.sweep]
    )
    if not sweep_edits:
        shell_output.emit("(no edits)", 0)
        return

    lines = []
    for product in sorted(sweep_edits, key=str.casefold):
        edits = sweep_edits[product]
        labels = ["start"] + [
            (
                "create"
                if isinstance(snapshot, dict)
                else "delete"
                if snapshot is None
                else "edit"
            )
            for snapshot in edits.snapshots
        ]
        cursor_position = edits.index + 1
        if 0 <= cursor_position < len(labels):
            labels[cursor_position] = "*" + labels[cursor_position]
        lines.extend((f"{product}:", f"  [{', '.join(labels)}]"))

    shell_output.emit("\n".join(lines), 0)


def _remove_edits(interaction_manager, shell_output: Any, args):
    if len(args) != 1:
        shell_output.emit(":rmedits requires one product name", 1)
        return

    window = interaction_manager.window
    requested = args[0].casefold()
    stored_name = next(
        (
            name
            for name in window.edit_manager.product_names()
            if name.casefold() == requested
        ),
        None,
    )
    affected_panels = []
    if stored_name is not None:
        for panel_index, panel in enumerate(window.state.panels):
            resolved = window.product_manager.resolve(panel.product)
            if (
                resolved is not None
                and resolved.raw_field.casefold() == stored_name.casefold()
            ):
                affected_panels.append(panel_index)

    removed = window.edit_manager.remove_history(args[0])
    if removed is None:
        shell_output.emit(
            f"No edits found for product {args[0]!r} in the current sweep",
            1,
        )
        return

    remaining = {
        name.casefold()
        for name in window.product_manager.available_products()
    }
    if removed.casefold() not in remaining:
        for panel_index in affected_panels:
            window.state.panels[panel_index].product = (
                window.product_manager.select_initial(panel_index)
            )
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
