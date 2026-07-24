"""Window-agnostic product listing and selection commands."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from frxxv.plotting.product import resolve_registered_product
from frxxv.state import ProductSpec


MAX_PRODUCT_TITLE_LENGTH = 10
DEFAULT_PRODUCT_TICKS = 5
_PRODUCT_ARGUMENT_COUNTS = (1, 3, 5, 6, 7)
_PRODUCT_USAGE = """Usage:
  :p PRODUCT
  :p RAW_FIELD SHORTHAND CMAP
  :p RAW_FIELD SHORTHAND CMAP VMIN VMAX
  :p RAW_FIELD SHORTHAND CMAP VMIN VMAX NTICKS
  :p RAW_FIELD SHORTHAND CMAP VMIN VMAX NTICKS UNITS

Custom VMIN and VMAX may both be empty strings to calculate fixed limits
from the current data. NTICKS defaults to 5. With one optional trailing
argument, an integer is NTICKS; any other value is UNITS."""


def execute(
    app_state,
    interaction_manager,
    shell_output: Any,
    action: str,
    *args: str,
):
    """List products or change the selected panel's product."""
    if action == "lp":
        _list_products(app_state, shell_output, args)
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

    panel.product = replace(panel.product, registered_name=None)
    shell_output.emit(
        f"Panel {panel_index} locked to {panel.product.raw_field}",
        0,
    )


def _list_products(app_state, shell_output: Any, args):
    if args:
        shell_output.emit(":lp does not accept arguments", 1)
        return

    data = app_state.scan_data
    if data is None:
        shell_output.emit("No file is currently loaded", 1)
        return

    products = data.products
    if not products:
        shell_output.emit("The current file has no products", 1)
        return

    shell_output.emit(
        "Available products:\n" + "\n".join(f"  {name}" for name in products),
        0,
    )


def _set_product(app_state, interaction_manager, shell_output: Any, args):
    if args == ("help",):
        shell_output.emit(_PRODUCT_USAGE, 0)
        return
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
        product = resolve_registered_product(data, args[0])
        if product is None:
            shell_output.emit(
                f"Product {args[0]!r} is unavailable or has no "
                "plot configuration",
                1,
            )
            return
    else:
        product = _parse_custom_product(data, shell_output, args)
        if product is None:
            return

    state.panels[panel_index].product = product
    state.panel_field_changed.emit(panel_index)


def _parse_custom_product(data, shell_output: Any, args):
    raw_field, title, cmap = args[:3]
    available = {name.casefold(): name for name in (data.products or ())}
    resolved_field = available.get(raw_field.casefold())
    if resolved_field is None:
        shell_output.emit(f"Raw product {raw_field!r} is unavailable", 1)
        return None

    if not title or len(title) > MAX_PRODUCT_TITLE_LENGTH:
        shell_output.emit(
            f"Product shorthand must contain 1–{MAX_PRODUCT_TITLE_LENGTH} "
            "characters\n" + _PRODUCT_USAGE,
            1,
        )
        return None

    if len(args) == 3:
        limits = _data_limits(data[resolved_field], shell_output)
        nticks = DEFAULT_PRODUCT_TICKS
        units = ""
    else:
        limits = _parse_limits(
            args[3],
            args[4],
            data[resolved_field],
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
