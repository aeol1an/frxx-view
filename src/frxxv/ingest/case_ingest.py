from abc import ABC, abstractmethod
from typing import List
from pathlib import Path

from .file_ingestible import FileIngestible

class CaseIngest(ABC):
    files: List[FileIngestible] = []
    current: int = 0

    @abstractmethod
    def __init__(self, directory: Path | str):
        self.directory = directory

    @abstractmethod
    def update():
        pass

    def get_next(self) -> FileIngestible:
        if len(self.files) == 0:
            raise IndexError("No files availible.")
        if self.current < 0 or self.current >= len(self.files):
            raise IndexError("Current file out of bounds.")
        
        if self.current == len(self.files)-1:
            return self.get_first()
        else:
            self.current += 1
            return self.files[self.current]
        
    def get_prev(self) -> FileIngestible:
        if len(self.files) == 0:
            raise IndexError("No files availible.")
        if self.current < 0 or self.current >= len(self.files):
            raise IndexError("Current file out of bounds.")
        
        if self.current == 0:
            return self.get_last()
        else:
            self.current -= 1
            return self.files[self.current]
        
    def get_first(self) -> FileIngestible:
        if len(self.files) == 0:
            raise IndexError("No files availible.")
        if self.current < 0 or self.current >= len(self.files):
            raise IndexError("Current file out of bounds.")
        
        self.current = 0
        return self.files[self.current]

    def get_last(self) -> FileIngestible:
        if len(self.files) == 0:
            raise IndexError("No files availible.")
        if self.current < 0 or self.current >= len(self.files):
            raise IndexError("Current file out of bounds.")
        
        self.current = len(self.files)-1
        return self.files[self.current]