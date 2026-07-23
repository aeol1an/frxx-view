"""Application-level case and sweep navigation."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject

from frxxv.ingest.case_ingest import CaseIngest
from frxxv.ingest.file_ingestible import FileIngestible
from frxxv.state import AppState


class FileManager(QObject):
    def __init__(self, state: AppState, parent: QObject | None = None):
        super().__init__(parent)
        self.state = state
        self.case: Optional[CaseIngest] = None
        self._loader: Optional[Callable[[Path], FileIngestible]] = None

    # ── Public API ──────────────────────────────────────────────────

    @property
    def current_file(self) -> Optional[Path]:
        if self.case is not None and self.case.files:
            return self.case.files[self.case.current]
        return None

    @property
    def file_count(self) -> int:
        return len(self.case.files) if self.case is not None else 0

    def set_loader(self, loader: Callable[[Path], FileIngestible]):
        """Register the lazy loader used when navigation changes files."""
        self._loader = loader

    def set_case(self, case: CaseIngest, initial_index: int = 0):
        """Set the program's case and load the requested initial file."""
        self.case = case
        self.state.case = case
        if case.files:
            if initial_index >= len(case.files):
                raise IndexError(
                    f"File index {initial_index} is out of bounds for "
                    f"a case with {len(case.files)} files"
                )
            case.current = initial_index
            self._load_current()
        elif initial_index != 0:
            raise IndexError(
                f"File index {initial_index} is out of bounds for an empty case"
            )

    def navigate(self, delta: int):
        """Move through sweeps, crossing file boundaries as needed."""
        if delta == 0 or self.case is None or not self.case.files:
            return
        for _ in range(abs(delta)):
            self._navigate_once(1 if delta > 0 else -1)

    def _navigate_once(self, direction: int):
        data = self.state.scan_data
        if data is None:
            self._load_current()
            return

        if direction > 0 and data.nextSweepAvail():
            data.sweep += 1
            self._update_scan_metadata(data)
            self.state.scan_changed.emit()
            return
        if direction < 0 and data.prevSweepAvail():
            data.sweep -= 1
            self._update_scan_metadata(data)
            self.state.scan_changed.emit()
            return

        if direction > 0:
            self.case.get_next()  # type: ignore[union-attr]
            self._load_current()
        else:
            self.case.get_prev()  # type: ignore[union-attr]
            self._load_current(use_last_sweep=True)

    def _load_current(self, use_last_sweep: bool = False):
        fp = self.current_file
        if fp is None or self._loader is None:
            return
        data = self._loader(fp)
        if use_last_sweep:
            data.sweep = data.nsweeps - 1
        self.state.scan_data = data
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
