from abc import ABC, abstractmethod
from pathlib import Path


class CaseIngest(ABC):
    files: list[Path] = []
    current: int = 0

    @abstractmethod
    def __init__(self, directory: Path | str):
        self.directory = directory

    @abstractmethod
    def update(self):
        pass

    def get_next(self) -> Path:
        if len(self.files) == 0:
            raise IndexError("No files availible.")
        if self.current < 0 or self.current >= len(self.files):
            raise IndexError("Current file out of bounds.")
        
        if self.current == len(self.files)-1:
            return self.get_first()
        else:
            self.current += 1
            return self.files[self.current]
        
    def get_prev(self) -> Path:
        if len(self.files) == 0:
            raise IndexError("No files availible.")
        if self.current < 0 or self.current >= len(self.files):
            raise IndexError("Current file out of bounds.")
        
        if self.current == 0:
            return self.get_last()
        else:
            self.current -= 1
            return self.files[self.current]
        
    def get_first(self) -> Path:
        if len(self.files) == 0:
            raise IndexError("No files availible.")
        if self.current < 0 or self.current >= len(self.files):
            raise IndexError("Current file out of bounds.")
        
        self.current = 0
        return self.files[self.current]

    def get_last(self) -> Path:
        if len(self.files) == 0:
            raise IndexError("No files availible.")
        if self.current < 0 or self.current >= len(self.files):
            raise IndexError("Current file out of bounds.")
        
        self.current = len(self.files)-1
        return self.files[self.current]
