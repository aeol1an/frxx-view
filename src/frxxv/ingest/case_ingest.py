from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional

from frxxv.ingest.file_ingestible import FileIngestible


class CaseIngest(ABC):
    def __init__(
        self,
        directory: Path | str,
        loader: Callable[[Path], FileIngestible],
    ):
        self.directory = Path(directory)
        self.files: list[Path] = []
        self.current = 0
        self.data: Optional[FileIngestible] = None
        self._loader = loader
        self.update()

    @abstractmethod
    def update(self):
        pass

    @property
    def current_file(self) -> Optional[Path]:
        if not self.files:
            return None
        return self.files[self.current]

    def load_file(self, index: int, last_sweep: bool = False):
        """Open a case file at its first or last sweep."""
        if index < 0 or index >= len(self.files):
            raise IndexError(
                f"File index {index} is out of bounds for "
                f"a case with {len(self.files)} files"
            )
        self.current = index
        self.data = self._loader(self.files[index])
        if last_sweep:
            self.data.lastSweep()
        else:
            self.data.firstSweep()

    def navigate_sweeps(self, delta: int) -> bool:
        """Move across sweeps and files without wrapping.

        Returns True when navigation was halted by a case boundary.
        """
        if delta == 0:
            return False
        if not self.files:
            return True
        if self.data is None:
            self.load_file(self.current)

        direction = 1 if delta > 0 else -1
        for _ in range(abs(delta)):
            assert self.data is not None
            if direction > 0:
                if self.data.nextSweep():
                    continue
                if self.current >= len(self.files) - 1:
                    return True
                self.load_file(self.current + 1)
            else:
                if self.data.prevSweep():
                    continue
                if self.current <= 0:
                    return True
                self.load_file(self.current - 1, last_sweep=True)
        return False
