"""Lazy, window-scoped storage for full-array product edits."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import pickle
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray


EditEntry = NDArray | dict[str, Any] | None


@dataclass
class Edits:
    """Linear snapshot history with an undo/redo cursor."""

    MAX_SNAPSHOTS: ClassVar[int] = 15

    snapshots: list[EditEntry] = field(default_factory=list)
    index: int = -1

    @property
    def has_current(self) -> bool:
        return 0 <= self.index < len(self.snapshots)

    @property
    def current(self) -> EditEntry:
        return self.snapshots[self.index] if self.has_current else None

    def append(self, snapshot: EditEntry):
        """Append after the cursor, discarding an abandoned redo branch."""
        del self.snapshots[self.index + 1:]
        self.snapshots.append(snapshot)
        while len(self.snapshots) > self.MAX_SNAPSHOTS:
            first_is_definition = isinstance(self.snapshots[0], dict)
            replacement_is_next = (
                len(self.snapshots) > 1
                and isinstance(self.snapshots[1], dict)
            )
            remove_at = 0 if not first_is_definition or replacement_is_next else 1
            del self.snapshots[remove_at]
        self.index = len(self.snapshots) - 1

    def undo(self) -> bool:
        if self.index < 0:
            return False
        self.index -= 1
        return True

    def redo(self) -> bool:
        if self.index >= len(self.snapshots) - 1:
            return False
        self.index += 1
        return True


EditHistory = list[dict[str, Edits]]


class EditManager:
    """Manage per-file, per-sweep replacement arrays for one data window."""

    EDIT_DIRECTORY = ".frxxv_edits"
    EDIT_SUFFIX = ".frxx_edited"

    def __init__(self, window):
        self.window = window
        self._active = self._edit_directory().is_dir()
        self._source: Path | None = None
        self._edit_history: EditHistory | None = None
        if self._active:
            self.activate()

    @property
    def active(self) -> bool:
        return self._active

    @property
    def edit_history(self) -> EditHistory | None:
        """Return the current file's edit history after editing is activated."""
        if not self._active:
            return None
        context = self._current_context()
        if context is None:
            return None
        source, ingestible = context
        return self._edit_history_for(source, ingestible.nsweeps)

    def edited_source_names(self) -> tuple[str, ...]:
        """Return source basenames represented by persisted edit histories."""
        directory = self._edit_directory()
        if not directory.is_dir():
            return ()
        suffix_length = len(self.EDIT_SUFFIX)
        return tuple(
            sorted(
                path.name[:-suffix_length]
                for path in directory.iterdir()
                if path.is_file() and path.name.endswith(self.EDIT_SUFFIX)
            )
        )

    def activate(self):
        """Enable edit lookup without creating files or directories."""
        self._active = True
        context = self._current_context()
        if context is not None:
            source, ingestible = context
            self._edit_history_for(source, ingestible.nsweeps)

    def record_edit(self, product: str, replacement: Any):
        """Append and persist a full replacement array for the current sweep."""
        self._append(product, np.asanyarray(replacement).copy())

    def record_deletion(self, product: str):
        """Append a deletion marker for the current product and sweep."""
        self._append(product, None)

    def record_new_product(self, product: str, full_product: dict[str, Any]):
        """Append a complete product definition at any history position."""
        self._append(product, deepcopy(full_product))

    def undo(self, product: str) -> bool:
        """Move one product history backward and persist its cursor."""
        context = self._require_context()
        self.activate()
        source, ingestible = context
        edit_history = self._edit_history_for(source, ingestible.nsweeps)
        sweep_edits = edit_history[ingestible.sweep]
        edits = sweep_edits.get(product)
        if edits is None or not edits.undo():
            return False
        self._persist(source, edit_history)
        return True

    def redo(self, product: str) -> bool:
        """Move one product history forward and persist its cursor."""
        context = self._require_context()
        self.activate()
        source, ingestible = context
        edit_history = self._edit_history_for(source, ingestible.nsweeps)
        edits = edit_history[ingestible.sweep].get(product)
        if edits is None or not edits.redo():
            return False
        self._persist(source, edit_history)
        return True

    def remove_history(self, product: str) -> str | None:
        """Remove one product's complete history from the current sweep."""
        if not self._active:
            return None
        context = self._current_context()
        if context is None:
            return None
        source, ingestible = context
        edit_history = self._edit_history_for(source, ingestible.nsweeps)
        sweep_edits = edit_history[ingestible.sweep]
        requested = product.casefold()
        stored_name = next(
            (name for name in sweep_edits if name.casefold() == requested),
            None,
        )
        if stored_name is None:
            return None
        del sweep_edits[stored_name]
        self._persist(source, edit_history)
        return stored_name

    def history(self, product: str) -> tuple[EditEntry, ...]:
        """Return a read-only snapshot of one current-sweep edit history."""
        if not self._active:
            return ()
        context = self._current_context()
        if context is None:
            return ()
        source, ingestible = context
        edit_history = self._edit_history_for(source, ingestible.nsweeps)
        edits = edit_history[ingestible.sweep].get(product)
        return () if edits is None else tuple(edits.snapshots)

    def latest(self, product: str) -> EditEntry:
        """Return the latest entry; ``None`` may mean deletion or no history."""
        found, entry = self._latest_entry(product)
        return entry if found else None

    def current_entry(self, product: str) -> tuple[bool, EditEntry]:
        """Return whether an edit is selected and its current snapshot."""
        return self._latest_entry(product)

    def product_names(self) -> tuple[str, ...]:
        """Return product names with histories in the current sweep."""
        if not self._active:
            return ()
        context = self._current_context()
        if context is None:
            return ()
        source, ingestible = context
        edit_history = self._edit_history_for(source, ingestible.nsweeps)
        return tuple(edit_history[ingestible.sweep])

    def product_definition(self, product: str) -> dict[str, Any] | None:
        """Return the latest full definition at or before the cursor."""
        if not self._active:
            return None
        context = self._current_context()
        if context is None:
            return None
        source, ingestible = context
        edit_history = self._edit_history_for(source, ingestible.nsweeps)
        edits = edit_history[ingestible.sweep].get(product)
        if edits is None or edits.index < 0:
            return None
        return next(
            (
                deepcopy(snapshot)
                for snapshot in reversed(edits.snapshots[:edits.index + 1])
                if isinstance(snapshot, dict)
            ),
            None,
        )

    def field(self, ingestible, product: str):
        """Return the latest replacement, or the original ingest field."""
        found, replacement = self._latest_entry(product)
        if not found:
            return ingestible[product]
        if replacement is None:
            raise KeyError(f"Product {product!r} is deleted in the edit history")
        if isinstance(replacement, dict):
            if "data" not in replacement:
                raise ValueError(
                    f"New product {product!r} has no 'data' member"
                )
            return replacement["data"]
        return replacement

    def _append(self, product: str, entry: EditEntry):
        context = self._require_context()
        self.activate()
        source, ingestible = context
        edit_history = self._edit_history_for(source, ingestible.nsweeps)
        edits = edit_history[ingestible.sweep].setdefault(product, Edits())
        edits.append(entry)
        self._persist(source, edit_history)

    def _latest_entry(self, product: str) -> tuple[bool, EditEntry]:
        if not self._active:
            return False, None
        context = self._current_context()
        if context is None:
            return False, None
        source, ingestible = context
        edit_history = self._edit_history_for(source, ingestible.nsweeps)
        edits = edit_history[ingestible.sweep].get(product)
        if edits is None or not edits.has_current:
            return False, None
        return True, edits.current

    def _current_context(self):
        case = self.window.state.case
        if case.current_file is None or case.data is None:
            return None
        return case.current_file.resolve(), case.data

    def _require_context(self):
        context = self._current_context()
        if context is None:
            raise RuntimeError("Cannot edit without a loaded file")
        return context

    def _edit_history_for(self, source: Path, nsweeps: int) -> EditHistory:
        if self._source == source and self._edit_history is not None:
            return self._normalize_edit_history(self._edit_history, nsweeps)

        edit_path = self._edit_path(source)
        if edit_path.exists():
            edit_history = self._load_edit_history(edit_path)
        else:
            edit_history = []

        edit_history = self._normalize_edit_history(edit_history, nsweeps)
        self._source = source
        self._edit_history = edit_history
        if not any(edit_history):
            self._persist(source, edit_history)
        return edit_history

    @classmethod
    def _load_edit_history(cls, edit_path: Path) -> EditHistory:
        """Unpickle and type-check one persisted edit history."""
        try:
            with edit_path.open("rb") as stream:
                edit_history = pickle.load(stream)
        except (
            pickle.UnpicklingError,
            EOFError,
            AttributeError,
            ImportError,
            IndexError,
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                f"Could not load edit history from {edit_path}: {error}"
            ) from error

        cls._validate_edit_history(edit_history, edit_path)
        return edit_history

    @staticmethod
    def _validate_edit_history(edit_history, edit_path: Path):
        """Require a list of sweep dictionaries containing Edits values."""
        if not isinstance(edit_history, list):
            raise ValueError(
                f"Invalid edit history in {edit_path}: expected a list"
            )

        for sweep_index, sweep_edits in enumerate(edit_history):
            if not isinstance(sweep_edits, dict):
                raise ValueError(
                    f"Invalid edit history in {edit_path}: sweep "
                    f"{sweep_index} is not a dictionary"
                )
            for product, edits in sweep_edits.items():
                if not isinstance(product, str):
                    raise ValueError(
                        f"Invalid edit history in {edit_path}: sweep "
                        f"{sweep_index} contains a non-string product name"
                    )
                if not isinstance(edits, Edits):
                    raise ValueError(
                        f"Invalid edit history in {edit_path}: product "
                        f"{product!r} in sweep {sweep_index} does not contain "
                        "an Edits history"
                    )
                if not isinstance(edits.snapshots, list):
                    raise ValueError(
                        f"Invalid edit history in {edit_path}: product "
                        f"{product!r} in sweep {sweep_index} has a non-list "
                        "snapshot history"
                    )
                if not isinstance(edits.index, int):
                    raise ValueError(
                        f"Invalid edit history in {edit_path}: product "
                        f"{product!r} in sweep {sweep_index} has a non-integer "
                        "history cursor"
                    )

    @classmethod
    def _normalize_edit_history(cls, edit_history, nsweeps: int) -> EditHistory:
        if len(edit_history) < nsweeps:
            edit_history.extend({} for _ in range(nsweeps - len(edit_history)))
        elif len(edit_history) > nsweeps:
            del edit_history[nsweeps:]

        for sweep_edits in edit_history:
            if not isinstance(sweep_edits, dict):
                raise ValueError(
                    "Every edit-history sweep must be a dictionary"
                )
            for product, edits in tuple(sweep_edits.items()):
                if isinstance(edits, Edits):
                    edits.index = min(
                        max(edits.index, -1),
                        len(edits.snapshots) - 1,
                    )
                else:
                    raise ValueError(
                        f"Product {product!r} has an invalid edit history"
                    )
        return edit_history

    def _persist(self, source: Path, edit_history: EditHistory):
        edit_path = self._edit_path(source)
        if not any(edit_history):
            edit_path.unlink(missing_ok=True)
            edit_directory = self._edit_directory()
            if edit_directory.is_dir():
                try:
                    edit_directory.rmdir()
                except OSError:
                    pass
            self._active = edit_directory.is_dir()
            self._source = None
            self._edit_history = None
            return

        edit_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = edit_path.with_name(edit_path.name + ".tmp")
        with temporary.open("wb") as stream:
            pickle.dump(edit_history, stream, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(edit_path)
        self._active = True
        self._source = source
        self._edit_history = edit_history

    def _edit_directory(self) -> Path:
        """Return the edit-history directory for the active case."""
        return self.window.state.case.directory / self.EDIT_DIRECTORY

    def _edit_path(self, source: Path) -> Path:
        return self._edit_directory() / (source.name + self.EDIT_SUFFIX)
