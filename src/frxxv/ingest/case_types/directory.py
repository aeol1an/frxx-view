from ..case_ingest import CaseIngest


class Directory(CaseIngest):
    def __init__(self, directory, loader, file_globs):
        self.file_globs = tuple(file_globs)
        super().__init__(directory, loader)

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
