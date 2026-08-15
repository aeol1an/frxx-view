"""Save the visible moment panels as one publication-ready PNG."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from frxx.viz import plotFigAsImg
from frxx.viz import polarGridPlotting
from frxx.viz.plotMoments import updatePPIAxesText
from frxxv.config import LAYOUTS, USER_CONFIG
from frxxv.ingest.case_types.directory import Directory


PANEL_WIDTH_INCHES = 2.5
OUTPUT_DPI = 300
MARGIN_PX = 1
TITLE_HEIGHT_INCHES = 0.22
GRID_LINE_WIDTH = 0.75
DEFAULT_AZIMUTH_INTERVAL = 60.0
DEFAULT_RANGE_INTERVAL = 3.0


def execute(
    app_state,
    interaction_manager,
    shell_output: Any,
    *args: str,
):
    """Render the visible panels without modifying their live figures."""
    if len(args) > 3:
        shell_output.emit(
            ":savefig accepts a filename, azimuth interval, and range interval",
            1,
        )
        return

    case = app_state.case
    if not isinstance(case, Directory):
        shell_output.emit(
            ":savefig is not implemented for "
            f"{type(case).__name__} cases",
            1,
        )
        return
    if case.current_file is None:
        shell_output.emit("No file is currently loaded", 1)
        return

    copied_figures = []
    output_figure = None
    try:
        from matplotlib import pyplot as plt
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        filename = _output_filename(args[0] if args else case.current_file.name)
        azimuth_interval = _azimuth_interval(args[1] if len(args) > 1 else None)
        range_interval = _range_interval(args[2] if len(args) > 2 else None)
        filename = _append_sweep_number(filename, app_state.scan_data)
        output_directory = (
            case.directory / USER_CONFIG.user_config["outdir"] / "img"
        )
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / filename

        positions = LAYOUTS.get(app_state.layout, LAYOUTS["2x2"])
        panel_states = app_state.panels[:len(positions)]
        if not panel_states or any(state.fig is None for state in panel_states):
            raise RuntimeError("The visible panels have not finished plotting")

        source_width, source_height = panel_states[0].fig.get_size_inches()
        if source_width <= 0 or source_height <= 0:
            raise ValueError("The visible panel has an invalid figure size")
        panel_height = PANEL_WIDTH_INCHES * source_height / source_width

        for state in panel_states:
            fig, ax, plot, cb = deepcopy(
                (state.fig, state.ax, state.plot, state.cb)
            )
            FigureCanvasAgg(fig)
            fig.set_size_inches(PANEL_WIDTH_INCHES, panel_height, forward=True)
            fig.set_dpi(OUTPUT_DPI)
            if azimuth_interval is not None:
                polarGridPlotting.azimuthSpiderweb(
                    ax,
                    azint=azimuth_interval,
                    lw=GRID_LINE_WIDTH,
                )
            if range_interval is not None:
                polarGridPlotting.rangeRings(
                    ax,
                    rint=range_interval,
                    lw=GRID_LINE_WIDTH,
                )
            updatePPIAxesText(
                fig,
                ax,
                plot,
                cb,
                PANEL_WIDTH_INCHES,
                panel_height,
            )
            copied_figures.append(fig)

        rows = max(row + rowspan for row, _, rowspan, _ in positions)
        columns = max(column + colspan for _, column, _, colspan in positions)
        content_width = columns * PANEL_WIDTH_INCHES
        content_height = rows * panel_height
        total_height = content_height + TITLE_HEIGHT_INCHES

        output_figure = plt.figure(
            figsize=(content_width, total_height),
            dpi=OUTPUT_DPI,
        )
        output_axes = output_figure.add_axes(
            (0, 0, 1, content_height / total_height)
        )
        plotFigAsImg(
            copied_figures,
            output_axes,
            marginPx=MARGIN_PX,
            srcVertical=app_state.layout == "1x2",
        )
        output_axes.axis("off")
        _add_info_title(output_figure, app_state.scan_metadata, content_height, total_height)

        output_figure.savefig(
            output_path,
            dpi=OUTPUT_DPI,
        )
        shell_output.emit(f"Saved {output_path}", 0)
    except Exception as error:
        shell_output.emit(str(error), 1)
    finally:
        if output_figure is not None:
            plt.close(output_figure)
        for figure in copied_figures:
            plt.close(figure)


def _output_filename(name: str) -> str:
    """Return a local PNG filename, preventing escape from the img folder."""
    if not name:
        raise ValueError("The figure name cannot be empty")
    if Path(name).name != name:
        raise ValueError(":savefig name must not contain a directory")
    return name if name.lower().endswith(".png") else f"{name}.png"


def _azimuth_interval(value: str | None) -> float | None:
    """Return a valid azimuth interval, or None when the grid is disabled."""
    interval = _interval(value, DEFAULT_AZIMUTH_INTERVAL, "azimuth")
    if interval is None:
        return None

    decimal_interval = Decimal(value) if value is not None else Decimal("60")
    if decimal_interval.as_tuple().exponent < -2:
        raise ValueError("Azimuth interval may have at most two decimal places")
    if Decimal("360") % decimal_interval != 0:
        raise ValueError("Azimuth interval must divide evenly into 360")
    return interval


def _range_interval(value: str | None) -> float | None:
    """Return a valid range-ring interval, or None when the grid is disabled."""
    return _interval(value, DEFAULT_RANGE_INTERVAL, "range")


def _interval(value: str | None, default: float, name: str) -> float | None:
    if value is None:
        return default
    if value == "None":
        return None
    try:
        interval = Decimal(value)
    except InvalidOperation as error:
        message = f"{name.capitalize()} interval must be a number or None"
        raise ValueError(message) from error
    if not interval.is_finite() or interval <= 0:
        raise ValueError(f"{name.capitalize()} interval must be greater than zero")
    return float(interval)


def _append_sweep_number(filename: str, ingestible) -> str:
    """Disambiguate images from different sweeps of one source file."""
    if ingestible is None:
        raise ValueError("No file is currently loaded")
    if ingestible.nsweeps <= 1:
        return filename
    path = Path(filename)
    return f"{path.stem}.{ingestible.sweep}{path.suffix}"


def _add_info_title(fig, metadata, content_height: float, total_height: float):
    title_y = (content_height + TITLE_HEIGHT_INCHES / 2) / total_height
    common = {
        "y": title_y,
        "va": "center",
        "fontsize": 7,
    }
    fig.text(
        0.01,
        s=metadata.get("instrument_name", ""),
        ha="left",
        fontweight="bold",
        **common,
    )
    fig.text(
        0.5,
        s=metadata.get("scan_time", ""),
        ha="center",
        **common,
    )
    fig.text(
        0.99,
        s=metadata.get("target_angle", ""),
        ha="right",
        **common,
    )
