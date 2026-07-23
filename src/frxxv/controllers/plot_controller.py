"""Centralized, persistent overlays for all radar panels."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class OverlaySpec:
    """A canvas-independent description of a Matplotlib overlay."""

    identifier: str
    kind: str
    x: Any
    y: Any
    style: dict[str, Any] = field(default_factory=dict)
    visible: bool = True


class PlotController:
    """Replicate persistent overlays across every registered panel."""

    def __init__(self, app_state):
        self.app_state = app_state
        self._overlays: dict[str, OverlaySpec] = {}
        self._panels: dict[int, tuple[Any, Any]] = {}
        self._artists: dict[int, dict[str, list[Any]]] = {}

    @property
    def overlays(self) -> tuple[OverlaySpec, ...]:
        return tuple(self._overlays.values())

    def plot(
        self,
        x,
        y,
        *,
        identifier: str | None = None,
        **style,
    ) -> str:
        """Add a line overlay to every panel and return its identifier."""
        return self.add("plot", x, y, identifier=identifier, **style)

    def scatter(
        self,
        x,
        y,
        *,
        identifier: str | None = None,
        **style,
    ) -> str:
        """Add a scatter overlay to every panel and return its identifier."""
        return self.add("scatter", x, y, identifier=identifier, **style)

    def add(
        self,
        kind: str,
        x,
        y,
        *,
        identifier: str | None = None,
        **style,
    ) -> str:
        """Store and render an overlay description."""
        if kind not in ("plot", "scatter"):
            raise ValueError("Overlay kind must be 'plot' or 'scatter'")

        overlay_id = identifier or uuid4().hex
        if overlay_id in self._overlays:
            raise ValueError(f"Overlay {overlay_id!r} already exists")

        spec = OverlaySpec(
            identifier=overlay_id,
            kind=kind,
            x=x,
            y=y,
            style=dict(style),
        )
        self._overlays[overlay_id] = spec
        self._render_overlay_on_all_panels(spec)
        return overlay_id

    def update(self, identifier: str, *, x=None, y=None, **style):
        """Replace coordinates or merge style values for an overlay."""
        spec = self._get_overlay(identifier)
        updated = replace(
            spec,
            x=spec.x if x is None else x,
            y=spec.y if y is None else y,
            style={**spec.style, **style},
        )
        self._overlays[identifier] = updated
        self._rerender_overlay(updated)

    def set_visible(self, identifier: str, visible: bool):
        """Show or hide an overlay on every panel."""
        spec = replace(self._get_overlay(identifier), visible=visible)
        self._overlays[identifier] = spec
        for panel_artists in self._artists.values():
            for artist in panel_artists.get(identifier, ()):
                artist.set_visible(visible)
        self._draw_all()

    def remove(self, identifier: str):
        """Remove an overlay specification and all of its live artists."""
        self._get_overlay(identifier)
        del self._overlays[identifier]
        for panel_index in tuple(self._artists):
            self._remove_panel_artists(panel_index, identifier)
        self._draw_all()

    def clear(self):
        """Remove all persistent overlays from every panel."""
        self._overlays.clear()
        for panel_index, panel_artists in self._artists.items():
            for identifier in tuple(panel_artists):
                self._remove_panel_artists(panel_index, identifier)
        self._draw_all()

    def rebuild_panel(self, panel_index: int, ax, canvas):
        """Register replacement axes and recreate every overlay on them."""
        self.unregister_panel(panel_index)
        self._panels[panel_index] = (ax, canvas)
        self._artists[panel_index] = {}
        for spec in self._overlays.values():
            self._render_overlay(panel_index, spec)
        canvas.draw_idle()

    def unregister_panel(self, panel_index: int):
        """Forget disposable artists belonging to an outgoing canvas."""
        self._panels.pop(panel_index, None)
        self._artists.pop(panel_index, None)

    def _render_overlay_on_all_panels(self, spec: OverlaySpec):
        for panel_index in tuple(self._panels):
            self._render_overlay(panel_index, spec)
        self._draw_all()

    def _render_overlay(self, panel_index: int, spec: OverlaySpec):
        ax, _canvas = self._panels[panel_index]
        autoscale = ax.get_autoscale_on()
        ax.set_autoscale_on(False)
        try:
            if spec.kind == "plot":
                artists = list(ax.plot(spec.x, spec.y, **spec.style))
            else:
                artists = [ax.scatter(spec.x, spec.y, **spec.style)]
        finally:
            ax.set_autoscale_on(autoscale)

        for artist in artists:
            artist.set_visible(spec.visible)
        self._artists[panel_index][spec.identifier] = artists

    def _rerender_overlay(self, spec: OverlaySpec):
        for panel_index in tuple(self._panels):
            self._remove_panel_artists(panel_index, spec.identifier)
            self._render_overlay(panel_index, spec)
        self._draw_all()

    def _remove_panel_artists(self, panel_index: int, identifier: str):
        panel_artists = self._artists.get(panel_index, {})
        for artist in panel_artists.pop(identifier, ()):
            try:
                artist.remove()
            except ValueError:
                pass

    def _draw_all(self):
        for _ax, canvas in self._panels.values():
            canvas.draw_idle()

    def _get_overlay(self, identifier: str) -> OverlaySpec:
        try:
            return self._overlays[identifier]
        except KeyError as error:
            raise KeyError(f"Unknown overlay {identifier!r}") from error
