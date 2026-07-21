from pathlib import Path

from ..case_ingest import CaseIngest


class Directory(CaseIngest):
    file_globs = ("cfrad.*.nc",)

    def __init__(self, directory: Path | str):
        self.directory = Path(directory)
        self.files: list[Path] = []
        self.current = 0
        self.update()

    def update(self):
        self.files = sorted(
            {
                path
                for file_glob in self.file_globs
                for path in self.directory.glob(file_glob)
                if path.is_file()
            }
        )

        if self.files:
            self.current = min(self.current, len(self.files) - 1)
        else:
            self.current = 0
