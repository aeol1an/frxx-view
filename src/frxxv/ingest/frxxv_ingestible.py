from abc import ABC, abstractmethod
from numpy.typing import NDArray

class FrxxvIngestible(ABC):
    sweep: int = 0
    nsweeps: int = 1

    def __getitem__(self, name) -> NDArray:
        return self.get_field(name)

    @abstractmethod
    def get_field(self, name) -> NDArray:
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
    def fixedAngle(self) -> float | int:
        pass

    @abstractmethod
    def nextSweepAvail(self) -> bool:
        pass

    @abstractmethod
    def prevSweepAvail(self) -> bool:
        pass