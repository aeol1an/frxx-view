from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from numpy.typing import NDArray

if TYPE_CHECKING:
    from frxxv.controllers.product_manager import ProductDefinition


class FileIngestible(ABC):
    sweep: int = 0
    nsweeps: int = 1
    products: list[str] | None = None
    data: Any = None
    overwritable: bool = False

    def __getitem__(self, name) -> NDArray:
        return self.get_field(name)

    @abstractmethod
    def get_field(self, name) -> NDArray:
        pass

    @abstractmethod
    def get_product(self, name: str) -> ProductDefinition:
        """Return a complete product definition, including its data."""
        pass

    @abstractmethod
    def fieldAvail(self, name: str) -> bool:
        pass

    @abstractmethod
    def write_full_file(self, filename: Path | str, edit_history=None) -> None:
        """Write the complete ingestible as one file."""
        pass

    @abstractmethod
    def write_sweeps(
        self,
        directory: Path | str,
        edit_history=None,
    ) -> tuple[Path, ...]:
        """Write one file per sweep and return the output paths."""
        pass

    @abstractmethod
    def constructTimeStr(self) -> str:
        pass

    @property
    @abstractmethod
    def instrumentName(self) -> str:
        pass
    
    @property
    @abstractmethod
    def rkm(self) -> NDArray:
        pass
    
    @property
    @abstractmethod
    def az(self) -> NDArray:
        pass
    
    @property
    @abstractmethod
    def el(self) -> NDArray:
        pass

    @property
    @abstractmethod
    def va(self) -> NDArray:
        """Nyquist velocity values for the current sweep."""
        pass

    @property
    @abstractmethod
    def ra(self) -> NDArray:
        """Unambiguous range values in meters for the current sweep."""
        pass

    @property
    @abstractmethod
    def pw(self) -> NDArray:
        """Pulse-width values for the current sweep."""
        pass

    @property
    @abstractmethod
    def prt(self) -> NDArray:
        """Pulse-repetition-time values for the current sweep."""
        pass

    @property
    @abstractmethod
    def wavelength(self) -> NDArray:
        """Radar wavelength values in meters."""
        pass
    
    @property
    @abstractmethod
    def fixedAngle(self) -> float | int:
        pass

    @abstractmethod
    def nextSweep(self) -> bool:
        """Advance one sweep, returning False at the end of the file."""
        pass

    @abstractmethod
    def prevSweep(self) -> bool:
        """Move back one sweep, returning False at the start of the file."""
        pass

    @abstractmethod
    def firstSweep(self):
        """Select the first sweep in the file."""
        pass

    @abstractmethod
    def lastSweep(self):
        """Select the last sweep in the file."""
        pass
