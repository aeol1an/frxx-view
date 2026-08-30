"""Accelerated pcolormesh rendering helpers."""

from functools import partial
from typing import Any

from ._pcolormesh import draw_quad_mesh as _draw_quad_mesh
from ._pcolormesh import hello_world

__all__ = ["hello_world", "install", "is_installed", "uninstall", "wrap_renderer"]

_original_update_methods = None
_installed = False


def _dispatch(native_draw_quad_mesh, *args):
    return _draw_quad_mesh(native_draw_quad_mesh, *args)


def wrap_renderer(renderer: Any) -> None:
    """Route an existing Agg renderer's quad meshes through this extension."""
    native_draw_quad_mesh = renderer._renderer.draw_quad_mesh
    renderer.draw_quad_mesh = partial(_dispatch, native_draw_quad_mesh)


def install() -> None:
    """Route quad meshes from subsequently created Agg renderers through C++."""
    global _installed, _original_update_methods

    if _installed:
        return

    from matplotlib.backends.backend_agg import RendererAgg

    _original_update_methods = RendererAgg._update_methods

    def update_methods(renderer):
        _original_update_methods(renderer)
        wrap_renderer(renderer)

    RendererAgg._update_methods = update_methods
    _installed = True


def uninstall() -> None:
    """Stop routing newly created Agg renderers through this extension.

    Renderers wrapped before this call remain wrapped.
    """
    global _installed, _original_update_methods

    if not _installed:
        return

    from matplotlib.backends.backend_agg import RendererAgg

    RendererAgg._update_methods = _original_update_methods
    _original_update_methods = None
    _installed = False


def is_installed() -> bool:
    """Return whether the Agg renderer hook is active."""
    return _installed
