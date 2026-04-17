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

def ppi_factory(panel_state, scan_data, width_inches, height_inches, dpi):
    """
    A PlotFactory compatible with PanelGrid.set_plot_factory().
    Uses create_test_figure for demonstration.
    """
    print(dpi)
    m: moments = frxxDataFromFile('/Volumes/RadarData/frxx-dev/m.nc')
    fig, ax, mesh, cb = plotPPI(
        m.RHOHV,
        title="RHOHV",
        units="RHOHV",
        rangesKM=m.rkm,
        azimuths=m.az,
        elevation=m.fixedAngle,
        width=width_inches, 
        aspectRatioWH=width_inches/height_inches,
        dpi = dpi,
        clims=(.2, 1.05, 5),
    )
    panel_state.fig      = fig
    panel_state.ax       = ax
    panel_state.plot     = mesh
    panel_state.cb       = cb
    panel_state.xlim     = tuple(ax.get_xlim())
    panel_state.ylim     = tuple(ax.get_ylim())
    panel_state.updater  = updatePPIAxesText