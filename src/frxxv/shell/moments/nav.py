"""Built-in commands for non-wrapping moment navigation."""
from __future__ import annotations

from typing import Any

import numpy as np

from frxxv.config import USER_CONFIG
from frxxv.state import ProductOverride


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
    action: int | str,
    *args: str,
):
    """Navigate by a sweep count or jump to a case boundary."""
    if action in ("begin", "end"):
        _go_to_boundary(app_state, shell_output, action, args)
        return
    if action == "n":
        _go_to_file(app_state, shell_output, args)
        return
    if action == "ls":
        _list_files(app_state, shell_output, args)
        return
    if action == "lp":
        _list_products(app_state, shell_output, args)
        return
    if action == "p":
        _set_product(
            app_state,
            interaction_manager,
            shell_output,
            args,
        )
        return

    if len(args) > 1:
        shell_output.emit("Navigation accepts at most one sweep count", 1)
        return

    try:
        count = int(args[0]) if args else 1
    except ValueError:
        shell_output.emit("Navigation sweep count must be an integer", 1)
        return

    if count < 0:
        shell_output.emit("Navigation sweep count cannot be negative", 1)
        return

    case = app_state.case
    if not case.files:
        shell_output.emit("Navigation halted: the case has no files", 1)
        return

    direction = int(action)
    halted = app_state.file_manager.navigate(direction * count)
    if halted:
        boundary = "end" if direction > 0 else "beginning"
        shell_output.emit(
            f"Navigation halted at the {boundary} of the case",
            1,
        )


def _go_to_boundary(app_state, shell_output: Any, boundary: str, args):
    if args:
        shell_output.emit(f":{boundary} does not accept arguments", 1)
        return

    case = app_state.case
    if not case.files:
        shell_output.emit("Navigation halted: the case has no files", 1)
        return

    if boundary == "begin":
        app_state.file_manager.load_file(0)
    else:
        app_state.file_manager.load_file(
            len(case.files) - 1,
            last_sweep=True,
        )


def _go_to_file(app_state, shell_output: Any, args):
    if len(args) != 1:
        shell_output.emit(":n requires one file number", 1)
        return

    try:
        file_number = int(args[0])
    except ValueError:
        shell_output.emit(":n file number must be an integer", 1)
        return

    case = app_state.case
    if file_number < 0 or file_number >= len(case.files):
        shell_output.emit(
            f"File number {file_number} is out of range "
            f"for a case with {len(case.files)} files",
            1,
        )
        return

    app_state.file_manager.load_file(file_number)


def _list_files(app_state, shell_output: Any, args):
    if args:
        shell_output.emit(":ls does not accept arguments", 1)
        return

    case = app_state.case
    if not case.files:
        shell_output.emit("The case has no files", 1)
        return

    lines = ["Case files:"]
    for index, path in enumerate(case.files):
        marker = "*" if index == case.current else " "
        lines.append(f"{marker} {index}: {path.name}")
    shell_output.emit("\n".join(lines), 0)


def _list_products(app_state, shell_output: Any, args):
    if args:
        shell_output.emit(":lp does not accept arguments", 1)
        return

    data = app_state.scan_data
    if data is None:
        shell_output.emit("No file is currently loaded", 1)
        return

    products = data.products()
    if not products:
        shell_output.emit("The current file has no products", 1)
        return

    shell_output.emit(
        "Available products:\n" + "\n".join(f"  {name}" for name in products),
        0,
    )


def _set_product(
    app_state,
    interaction_manager,
    shell_output: Any,
    args,
):
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

    panel_state = state.panels[panel_index]
    if len(args) == 1:
        requested = args[0]
        configured_product = _resolve_product(requested, data.products())
        if configured_product is None:
            shell_output.emit(
                f"Product {requested!r} is unavailable or has no "
                "plot configuration",
                1,
            )
            return
        panel_state.field_name = configured_product
        panel_state.product_override = None
    else:
        override = _parse_product_override(data, shell_output, args)
        if override is None:
            return
        panel_state.field_name = override.title
        panel_state.product_override = override

    state.panel_field_changed.emit(panel_index)


def _parse_product_override(data, shell_output: Any, args):
    raw_field, title, cmap = args[:3]
    available = {name.casefold(): name for name in data.products()}
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
        optional = args[5:]
        parsed_optional = _parse_ticks_and_units(optional, shell_output)
        if parsed_optional is None:
            return None
        nticks, units = parsed_optional

    if limits is None:
        return None
    vmin, vmax = limits
    return ProductOverride(
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


def _resolve_product(requested: str, available: list[str]) -> str | None:
    requested_key = requested.casefold()
    available_keys = {name.casefold() for name in available}

    for product, config in USER_CONFIG.user_config["products"].items():
        aliases = config["priority"]
        requested_matches = requested_key == product.casefold() or any(
            requested_key == alias.casefold() for alias in aliases
        )
        file_matches = any(
            alias.casefold() in available_keys for alias in aliases
        )
        if requested_matches and file_matches:
            return product
    return None
