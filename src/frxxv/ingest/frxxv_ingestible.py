from abc import ABC, abstractmethod
class FrxxvIngestible(ABC):
    sweep: int = 0
    nsweeps: int = 1

    def __getitem__(self, name):
        return self.get_field(name)

    @abstractmethod
    def get_field(self, name):
        pass
    
    @property
    @abstractmethod
    def rkm(self):
        pass
    
    @property
    @abstractmethod
    def az(self):
        pass
    
    @property
    @abstractmethod
    def el(self):
        pass
    
    @property
    @abstractmethod
    def fixedAngle(self):
        pass

    @abstractmethod
    def nextSweepAvail(self) -> bool:
        pass

    @abstractmethod
    def prevSweepAvail(self) -> bool:
        pass