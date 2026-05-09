"""
Central application state.

All shared mutable state lives in AppState.  Widgets observe it via
Qt signals — they never talk to each other directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable

from PySide6.QtCore import QObject, Signal

from frxxv.config import DEFAULT_LAYOUT, NUM_PANELS
from frxxv.ingest.file_ingestible import FileIngestible

@dataclass
class PanelState:
    """Per-panel mutable state.  Always NUM_PANELS of these in AppState.panels."""
    #Set prior to factory creation
    field_name: str = ""

    #Set by the factory
    fig: Any  = None          # matplotlib Figure
    ax: Any   = None          # matplotlib Axes
    plot: Any = None          # primary artist (QuadMesh, etc.)
    cb: Any   = None          # Colorbar (or None)
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None
    updater: Optional[Callable] = None

    #set after factory to handle resizes
    w: int | None = None
    h: int | None = None
    


class AppState(QObject):
    # ── Signals ─────────────────────────────────────────────────────
    layout_changed      = Signal(str)     # new layout key
    selection_changed   = Signal(object)  # Optional[int]
    scan_changed        = Signal()        # new scan data loaded
    panel_field_changed = Signal(int)     # index of panel whose field changed
    type: str       = ""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._layout: str = DEFAULT_LAYOUT
        self._selected: Optional[int] = None
        self.panels: List[PanelState] = [PanelState() for _ in range(NUM_PANELS)]

        # Populated by the user's file-loader callback
        self.scan_data: Optional[FileIngestible] = None
        self.scan_metadata: Dict[str, str] = {
            "radar_name": "",
            "scan_time": "",
        }

    # ── layout property ─────────────────────────────────────────────
    @property
    def layout(self) -> str:
        return self._layout

    @layout.setter
    def layout(self, value: str):
        if value != self._layout:
            self._layout = value
            self.layout_changed.emit(value)

    # ── selected property ───────────────────────────────────────────
    @property
    def selected(self) -> Optional[int]:
        return self._selected

    @selected.setter
    def selected(self, value: Optional[int]):
        if value != self._selected:
            self._selected = value
            self.selection_changed.emit(value)