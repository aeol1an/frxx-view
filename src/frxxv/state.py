"""
Central application state.

All shared mutable state lives in AppState.  Widgets observe it via
Qt signals — they never talk to each other directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Callable
from numpy.typing import NDArray

from PySide6.QtCore import QObject, Signal

from frxxv.config import DEFAULT_LAYOUT, LAYOUTS, NUM_PANELS
from frxxv.ingest.file_ingestible import FileIngestible

if TYPE_CHECKING:
    from frxxv.controllers.file_manager import FileManager
    from frxxv.ingest.case_ingest import CaseIngest
    from frxxv.windows.data_window import DataWindow

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
    grid: Optional[Tuple[NDArray, NDArray]] = None
    data: Optional[NDArray] = None
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
    panel_double_clicked = Signal(dict)   # nearest gate information
    type: str       = ""

    def __init__(
        self,
        starting_directory: Path,
        initial_index: int = 0,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.starting_directory = starting_directory.expanduser().resolve()
        self._layout: str = DEFAULT_LAYOUT
        self._selected: Optional[int] = None
        self.panels: List[PanelState] = [PanelState() for _ in range(NUM_PANELS)]
        self.type = "ppi"

        # Populated by the user's file-loader callback
        self.scan_data: Optional[FileIngestible] = None
        self.scan_metadata: Dict[str, str] = {
            "instrument_name": "",
            "scan_time": "",
            "target_angle": "",
        }

        # Import locally because these application objects all depend on
        # AppState. AppState owns their construction and lifetime.
        from frxxv.controllers.file_manager import FileManager
        from frxxv.ingest.case_types.directory import Directory
        from frxxv.ingest.file_types.pyart import PyartFile
        from frxxv.plotting.ppi import ppi_factory
        from frxxv.windows.data_window import DataWindow

        case_directory_found = (
            self.starting_directory / "frxx_cases"
        ).is_dir()
        self.case: "CaseIngest" = Directory(self.starting_directory)
        self.file_manager: "FileManager" = FileManager(self, self)
        self.file_manager.set_loader(PyartFile)

        self.main_window: "DataWindow" = DataWindow(
            "Frxx View",
            state=self,
        )

        fields = ["DBZ", "VEL", "ZDR", "RHOHV"]
        visible = len(LAYOUTS[self.layout])
        for i in range(visible):
            panel = self.main_window.panel_grid.panels[i]
            panel.state.field_name = fields[i]
            panel.set_plot_factory(ppi_factory)

        if case_directory_found:
            self.main_window.shell_output.emit(
                "frxx_cases is not implemented; treating as a directory",
                1,
            )

        self.file_manager.set_case(self.case, initial_index=initial_index)
        self.main_window.show()

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
