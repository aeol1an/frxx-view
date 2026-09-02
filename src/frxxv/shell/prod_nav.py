"""Window-agnostic product listing and selection commands."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from frxxv.shell.help import detailed_help
from frxxv.state import ProductSpec


MAX_PRODUCT_TITLE_LENGTH = 10
DEFAULT_PRODUCT_TICKS = 5
_PRODUCT_ARGUMENT_COUNTS = (1, 3, 5, 6, 7)
_PRODUCT_USAGE = detailed_help("p")
assert _PRODUCT_USAGE is not None


def execute(
    app_state,
    interaction_manager,
    shell_output: Any,
    action: str,
    *args: str,
):
    """List products or change the selected panel's product."""
    if action == "lp":
        _list_products(app_state, interaction_manager, shell_output, args)
    elif action == "lock":
        _lock_product(interaction_manager, shell_output, args)
    else:
        _set_product(app_state, interaction_manager, shell_output, args)


def _lock_product(interaction_manager, shell_output: Any, args):
    if args:
        shell_output.emit(":lock does not accept arguments", 1)
        return

    state = interaction_manager.window.state
    panel_index = state.selected
    if panel_index is None:
        shell_output.emit(":lock requires a selected panel", 1)
        return

    panel = state.panels[panel_index]
    if panel.product is None:
        shell_output.emit("The selected panel has no product to lock", 1)
        return

    resolved = interaction_manager.window.product_manager.resolve(panel.product)
    if resolved is None:
        shell_output.emit("The selected panel product cannot be resolved", 1)
        return
    panel.product = replace(
        panel.product,
        raw_field=resolved.raw_field,
        registered_name=None,
    )


def _list_products(app_state, interaction_manager, shell_output: Any, args):
    if args:
        shell_output.emit(":lp does not accept arguments", 1)
        return

    data = app_state.scan_data
    if data is None:
        shell_output.emit("No file is currently loaded", 1)
        return

    products = interaction_manager.window.product_manager.available_products()
    if not products:
        shell_output.emit("The current file has no products", 1)
        return

    shell_output.emit(
        "Available products:\n" + "\n".join(f"  {name}" for name in products),
        0,
    )


def _set_product(app_state, interaction_manager, shell_output: Any, args):
    if len(args) not in _PRODUCT_ARGUMENT_COUNTS:
        shell_output.emit(_PRODUCT_USAGE, 1)
        return

    state = interaction_manager.window.state
    panel_index = state.selected
    if panel_index is None:
        shell_output.emit(":p requires a selected panel", 1)
        return

    data = app_state.scan_data
    if data is None:
        shell_output.emit("No file is currently loaded", 1)
        return

    if len(args) == 1:
        product = interaction_manager.window.product_manager.select_registered(
            args[0]
        )
        if product is None:
            shell_output.emit(
                f"Product {args[0]!r} is unavailable or has no "
                "plot configuration",
                1,
            )
            return
    else:
        product = _parse_custom_product(
            interaction_manager.window.product_manager,
            shell_output,
            args,
        )
        if product is None:
            return

    state.panels[panel_index].product = product
    state.panel_field_changed.emit(panel_index)


def _parse_custom_product(product_manager, shell_output: Any, args):
    raw_field, title, cmap_name = args[:3]
    resolved = product_manager.resolve_raw(raw_field)
    if resolved is None:
        resolved_field = raw_field
        product_data = None
    else:
        resolved_field, product_data = resolved

    if not title or len(title) > MAX_PRODUCT_TITLE_LENGTH:
        shell_output.emit(
            f"Product shorthand must contain 1–{MAX_PRODUCT_TITLE_LENGTH} "
            "characters\n" + _PRODUCT_USAGE,
            1,
        )
        return None

    cmap = _resolve_colormap(cmap_name, shell_output)
    if cmap is None:
        return None

    if len(args) == 3:
        limits = _data_limits(product_data, shell_output)
        nticks = DEFAULT_PRODUCT_TICKS
        units = ""
    else:
        limits = _parse_limits(
            args[3],
            args[4],
            product_data,
            shell_output,
        )
        parsed_optional = _parse_ticks_and_units(args[5:], shell_output)
        if parsed_optional is None:
            return None
        nticks, units = parsed_optional

    if limits is None:
        return None
    vmin, vmax = limits
    return ProductSpec(
        raw_field=resolved_field,
        title=title,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        nticks=nticks,
        units=units,
    )


def _resolve_colormap(requested: str, shell_output: Any):
    """Resolve a custom product's colormap from the live Matplotlib registry."""
    try:
        import cmweather  # noqa: F401
    except ImportError:
        pass

    from matplotlib import colormaps

    try:
        return colormaps[requested]
    except KeyError:
        shell_output.emit(f"Colormap {requested!r} was not found", 1)
        return None


def _parse_limits(vmin_text, vmax_text, values, shell_output: Any):
    if not vmin_text and not vmax_text:
        return _data_limits(values, shell_output)
    if not vmin_text or not vmax_text:
        shell_output.emit(
            "VMIN and VMAX must either both be provided or both be empty\n"
            + _PRODUCT_USAGE,
            1,
        )
        return None
    try:
        vmin = float(vmin_text)
        vmax = float(vmax_text)
    except ValueError:
        shell_output.emit("VMIN and VMAX must be numbers\n" + _PRODUCT_USAGE, 1)
        return None
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
        shell_output.emit(
            "VMIN and VMAX must be finite, with VMIN less than VMAX\n"
            + _PRODUCT_USAGE,
            1,
        )
        return None
    return vmin, vmax


def _data_limits(values, shell_output: Any):
    if values is None:
        shell_output.emit(
            "Cannot calculate limits: product is unavailable; "
            "provide explicit VMIN and VMAX",
            1,
        )
        return None
    finite = np.ma.masked_invalid(np.ma.asarray(values)).compressed()
    if finite.size == 0:
        shell_output.emit("Cannot calculate limits: product has no finite data", 1)
        return None
    vmin = float(finite.min())
    vmax = float(finite.max())
    if vmin == vmax:
        shell_output.emit("Cannot calculate limits from constant-valued data", 1)
        return None
    return vmin, vmax


def _parse_ticks_and_units(optional, shell_output: Any):
    nticks = DEFAULT_PRODUCT_TICKS
    units = ""
    if len(optional) == 1:
        value = optional[0]
        if value:
            try:
                nticks = int(value)
            except ValueError:
                units = value
    elif len(optional) == 2:
        ticks_text, units = optional
        if ticks_text:
            try:
                nticks = int(ticks_text)
            except ValueError:
                shell_output.emit("NTICKS must be an integer\n" + _PRODUCT_USAGE, 1)
                return None

    if nticks < 1:
        shell_output.emit("NTICKS must be positive\n" + _PRODUCT_USAGE, 1)
        return None
    return nticks, units
