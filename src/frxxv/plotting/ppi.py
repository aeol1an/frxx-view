"""
Placeholder plotting module.

create_test_figure  — generates a fake PPI for testing the framework.
demo_plot_factory   — a PlotFactory-compatible wrapper around it.

Replace or adapt these with your real plotPPI.
"""
from __future__ import annotations

from frxx.viz.plotMoments import plotPPI, updatePPIAxesText

def ppi_factory(
    panel_state,
    app_state,
    width_inches,
    height_inches,
    dpi,
    window,
):
    """
    A PlotFactory compatible with PanelGrid.set_plot_factory().
    Uses create_test_figure for demonstration.
    """
    data = app_state.scan_data
    product = panel_state.product
    resolved = window.product_manager.resolve(product)
    if data is None or resolved is None:
        return

    y_center = None
    if panel_state.ylim is not None:
        y_center = (panel_state.ylim[0] + panel_state.ylim[1]) / 2

    fig, ax, mesh, cb, grid = plotPPI(
        resolved.data,
        title=resolved.title,
        units=resolved.units,
        rangesKM=data.rkm,
        azimuths=data.az,
        elevation=data.fixedAngle,
        width=width_inches, 
        aspectRatioWH=width_inches/height_inches,
        dpi = dpi,
        xlim=panel_state.xlim,
        yCenter=y_center,
        clims=(resolved.vmin, resolved.vmax, resolved.nticks),
        cmap=resolved.cmap,
        backend=False
    )
    panel_state.fig      = fig
    panel_state.ax       = ax
    panel_state.plot     = mesh
    panel_state.cb       = cb
    panel_state.grid     = grid
    panel_state.data     = resolved.data
    panel_state.xlim     = tuple(ax.get_xlim())
    panel_state.ylim     = tuple(ax.get_ylim())
    panel_state.updater  = updatePPIAxesText
