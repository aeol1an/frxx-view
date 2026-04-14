"""
Placeholder plotting module.

create_test_figure  — generates a fake PPI for testing the framework.
demo_plot_factory   — a PlotFactory-compatible wrapper around it.

Replace or adapt these with your real plotPPI.
"""
from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure


def create_test_figure(
    width: float = 2.0,
    height: float = 2.83,
    dpi: float = 100,
) -> tuple:
    """Quick synthetic PPI for layout testing.  Returns (fig, ax, mesh, None)."""
    fig = Figure(figsize=(width, height), dpi=dpi)
    ax = fig.add_subplot(111)

    r = np.linspace(0, 100, 120)
    theta = np.linspace(0, 2 * np.pi, 360)
    R, T = np.meshgrid(r, theta)
    X = R * np.cos(T)
    Y = R * np.sin(T)
    Z = np.sin(R / 15) * np.cos(T * 3)

    mesh = ax.pcolormesh(X, Y, Z, shading="auto", cmap="viridis")
    ax.set_aspect("equal")
    ax.set_xlim(-100, 100)
    ax.set_ylim(-100, 100)
    fig.tight_layout()

    return fig, ax, mesh, None


def demo_plot_factory(panel_state, scan_data, width_inches, height_inches, dpi):
    """
    A PlotFactory compatible with PanelGrid.set_plot_factory().
    Uses create_test_figure for demonstration.
    """
    fig, ax, mesh, cb = create_test_figure(width_inches, height_inches, dpi)
    panel_state.fig      = fig
    panel_state.ax       = ax
    panel_state.plot     = mesh
    panel_state.cb       = cb
    panel_state.xlim     = tuple(ax.get_xlim())
    panel_state.y_center = sum(ax.get_ylim()) / 2.0