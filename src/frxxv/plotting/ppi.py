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

def ppi_factory(panel_state, width_inches, height_inches, dpi):
    """
    A PlotFactory compatible with PanelGrid.set_plot_factory().
    Uses create_test_figure for demonstration.
    """
    field = panel_state.field
    m: moments = frxxDataFromFile('/Volumes/RadarData/frxx-dev/m.nc')
    fig, ax, mesh, cb = plotPPI(
        scan_data[field].data,
        title=field,
        units=dpp.moments[field]["units"],
        rangesKM=scan_data["range"].data/1000.,
        azimuths=scan_data["az"],
        elevation=m.fixedAngle,
        width=width_inches, 
        aspectRatioWH=width_inches/height_inches,
        dpi = dpi,
        clims=dpp.moments[field]["ranges"],
        cmap=dpp.moments[field]["cmap"]
    )
    panel_state.type     = "ppi"
    panel_state.fig      = fig
    panel_state.ax       = ax
    panel_state.plot     = mesh
    panel_state.cb       = cb
    panel_state.xlim     = tuple(ax.get_xlim())
    panel_state.ylim     = tuple(ax.get_ylim())
    panel_state.updater  = updatePPIAxesText