"""Application-level case and sweep navigation."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject

from frxxv.ingest.case_ingest import CaseIngest
from frxxv.ingest.file_ingestible import FileIngestible
from frxxv.state import AppState


class FileManager(QObject):
    def __init__(self, state: AppState, parent: QObject | None = None):
        super().__init__(parent)
        self.state = state

    # ── Public API ──────────────────────────────────────────────────

    @property
    def case(self) -> CaseIngest:
        return self.state.case

    @property
    def current_file(self) -> Optional[Path]:
        return self.case.current_file

    @property
    def file_count(self) -> int:
        return len(self.case.files)

    def set_case(self, case: CaseIngest, initial_index: int = 0):
        """Set the program's case and load the requested initial file."""
        self.state.case = case
        if case.files:
            if initial_index < 0 or initial_index >= len(case.files):
                raise IndexError(
                    f"File index {initial_index} is out of bounds for "
                    f"a case with {len(case.files)} files"
                )
            case.load_file(initial_index)
            self._publish_scan_change()
        elif initial_index != 0:
            raise IndexError(
                f"File index {initial_index} is out of bounds for an empty case"
            )

    def navigate(self, delta: int) -> bool:
        """Move through sweeps, crossing file boundaries as needed."""
        halted = self.case.navigate_sweeps(delta)
        if self.case.data is not None:
            self._publish_scan_change()
        return halted

    def load_file(self, index: int, last_sweep: bool = False):
        """Load a file by index at its first or last sweep."""
        if not self.case.files:
            return
        if index < 0 or index >= len(self.case.files):
            raise IndexError(
                f"File index {index} is out of bounds for "
                f"a case with {len(self.case.files)} files"
            )
        self.case.load_file(index, last_sweep=last_sweep)
        self._publish_scan_change()

    def _publish_scan_change(self):
        if self.case.data is None:
            return
        data = self.case.data
        self._update_scan_metadata(data)
        self.state.scan_changed.emit()

    def _update_scan_metadata(self, data: FileIngestible):
        angle_name = {
            "ppi": "EL",
            "rhi": "AZ",
        }.get(self.state.type.lower(), "")
        target_angle = (
            f"{angle_name}={float(data.fixedAngle):.1f}°"
            if angle_name else ""
        )
        self.state.scan_metadata = {
            "instrument_name": data.instrumentName,
            "scan_time": data.constructTimeStr(),
            "target_angle": target_angle,
        }
