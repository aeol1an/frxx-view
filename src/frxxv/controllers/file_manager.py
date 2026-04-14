"""
File list management, prev/next navigation, and periodic polling
for new files in a directory.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import QTimer, QObject

from frxxv.config import DEFAULT_POLL_INTERVAL_MS
from frxxv.state import AppState


class FileManager(QObject):
    def __init__(self, state: AppState, parent: QObject | None = None):
        super().__init__(parent)
        self.state = state

        self._directory: Optional[Path] = None
        self._glob: str = "*"
        self._files: List[Path] = []
        self._current_index: int = -1

        # User-supplied callback:  loader(filepath) -> None
        # Should populate state.scan_data and state.scan_metadata.
        self._loader: Optional[Callable[[Path], None]] = None

        # Poll timer (not started by default)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(DEFAULT_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self.poll)

    # ── Public API ──────────────────────────────────────────────────

    @property
    def current_file(self) -> Optional[Path]:
        if 0 <= self._current_index < len(self._files):
            return self._files[self._current_index]
        return None

    @property
    def file_count(self) -> int:
        return len(self._files)

    def set_loader(self, loader: Callable[[Path], None]):
        """
        Register a file-loading callback.

        The loader should populate self.state.scan_data and
        self.state.scan_metadata; FileManager will emit scan_changed.
        """
        self._loader = loader

    def set_directory(self, path: str | Path, glob: str = "*"):
        """Point at a directory and refresh the file list."""
        self._directory = Path(path)
        self._glob = glob
        self._refresh_file_list()
        if self._files:
            self._current_index = 0
            self._load_current()

    def navigate(self, delta: int):
        """Move forward (+) or backward (−) in the file list."""
        if not self._files:
            return
        new = max(0, min(self._current_index + delta, len(self._files) - 1))
        if new != self._current_index:
            self._current_index = new
            self._load_current()

    def start_polling(self, interval_ms: int | None = None):
        if interval_ms is not None:
            self._poll_timer.setInterval(interval_ms)
        self._poll_timer.start()

    def stop_polling(self):
        self._poll_timer.stop()

    def poll(self):
        """Check for new files.  Called by the timer or manually."""
        old_count = len(self._files)
        self._refresh_file_list()
        if len(self._files) > old_count:
            # New files appeared — subclass or monkey-patch to customize
            pass

    # ── Internals ───────────────────────────────────────────────────

    def _refresh_file_list(self):
        if self._directory is None or not self._directory.exists():
            self._files = []
            return
        self._files = sorted(self._directory.glob(self._glob))

    def _load_current(self):
        fp = self.current_file
        if fp is None:
            return
        if self._loader is not None:
            self._loader(fp)
        self.state.scan_changed.emit()