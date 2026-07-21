"""
Placeholder plotting module.

create_test_figure  — generates a fake PPI for testing the framework.
demo_plot_factory   — a PlotFactory-compatible wrapper around it.

Replace or adapt these with your real plotPPI.
"""
from __future__ import annotations

from frxx.core import moments
from frxx.io.caseManager import frxxDataFromFile
from frxx.viz.plotMoments import plotPPI, updatePPIAxesText

from frxxv.config import USER_CONFIG
from frxxv.ingest.file_ingestible import FileIngestible

def ppi_factory(panel_state, app_state, width_inches, height_inches, dpi):
    """
    A PlotFactory compatible with PanelGrid.set_plot_factory().
    Uses create_test_figure for demonstration.
    """
    field = panel_state.field_name
    data: FileIngestible = app_state.scan_data
    product_config = USER_CONFIG.user_config["products"][field]
    y_center = None
    if panel_state.ylim is not None:
        y_center = (panel_state.ylim[0] + panel_state.ylim[1]) / 2

    fig, ax, mesh, cb = plotPPI(
        data[field],
        title=field,
        units=product_config["units"],
        rangesKM=data.rkm,
        azimuths=data.az,
        elevation=data.fixedAngle,
        width=width_inches, 
        aspectRatioWH=width_inches/height_inches,
        dpi = dpi,
        xlim=panel_state.xlim,
        yCenter=y_center,
        clims=product_config["clims"],
        cmap=product_config["cmap"],
        backend=False
    )
    panel_state.fig      = fig
    panel_state.ax       = ax
    panel_state.plot     = mesh
    panel_state.cb       = cb
    panel_state.xlim     = tuple(ax.get_xlim())
    panel_state.ylim     = tuple(ax.get_ylim())
    panel_state.updater  = updatePPIAxesText
