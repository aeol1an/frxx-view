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

import frxx.viz.defaultPlotParameters as dpp

from frxxv.ingest.file_ingestible import FileIngestible

def ppi_factory(panel_state, app_state, width_inches, height_inches, dpi):
    """
    A PlotFactory compatible with PanelGrid.set_plot_factory().
    Uses create_test_figure for demonstration.
    """
    field = panel_state.field_name
    data: FileIngestible = app_state.scan_data

    fig, ax, mesh, cb = plotPPI(
        data[field],
        title=field,
        units=dpp.moments[field]["units"],
        rangesKM=data.rkm,
        azimuths=data.az,
        elevation=data.fixedAngle,
        width=width_inches, 
        aspectRatioWH=width_inches/height_inches,
        dpi = dpi,
        clims=dpp.moments[field]["ranges"],
        cmap=dpp.moments[field]["cmap"]
    )
    panel_state.fig      = fig
    panel_state.ax       = ax
    panel_state.plot     = mesh
    panel_state.cb       = cb
    panel_state.xlim     = tuple(ax.get_xlim())
    panel_state.ylim     = tuple(ax.get_ylim())
    panel_state.updater  = updatePPIAxesText