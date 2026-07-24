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


EditSchema = list[dict[str, Edits]]


class EditManager:
    """Manage per-file, per-sweep replacement arrays for one data window."""

    EDIT_DIRECTORY = ".frxxv_edits"
    EDIT_SUFFIX = ".frxx_edited"

    def __init__(self, window):
        self.window = window
        self._active = self._edit_directory().is_dir()
        self._source: Path | None = None
        self._schema: EditSchema | None = None
        if self._active:
            self.activate()

    @property
    def active(self) -> bool:
        return self._active

    @property
    def schema(self) -> EditSchema | None:
        """Return the current file's schema after editing is activated."""
        if not self._active:
            return None
        context = self._current_context()
        if context is None:
            return None
        source, ingestible = context
        return self._schema_for(source, ingestible.nsweeps)

    def activate(self):
        """Enable edit lookup without creating files or directories."""
        self._active = True
        context = self._current_context()
        if context is not None:
            source, ingestible = context
            self._schema_for(source, ingestible.nsweeps)

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
        schema = self._schema_for(source, ingestible.nsweeps)
        sweep_edits = schema[ingestible.sweep]
        edits = sweep_edits.get(product)
        if edits is None or not edits.undo():
            return False
        self._persist(source, schema)
        return True

    def redo(self, product: str) -> bool:
        """Move one product history forward and persist its cursor."""
        context = self._require_context()
        self.activate()
        source, ingestible = context
        schema = self._schema_for(source, ingestible.nsweeps)
        edits = schema[ingestible.sweep].get(product)
        if edits is None or not edits.redo():
            return False
        self._persist(source, schema)
        return True

    def history(self, product: str) -> tuple[EditEntry, ...]:
        """Return a read-only snapshot of one current-sweep edit history."""
        if not self._active:
            return ()
        context = self._current_context()
        if context is None:
            return ()
        source, ingestible = context
        schema = self._schema_for(source, ingestible.nsweeps)
        edits = schema[ingestible.sweep].get(product)
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
        schema = self._schema_for(source, ingestible.nsweeps)
        return tuple(schema[ingestible.sweep])

    def product_definition(self, product: str) -> dict[str, Any] | None:
        """Return the latest full definition at or before the cursor."""
        if not self._active:
            return None
        context = self._current_context()
        if context is None:
            return None
        source, ingestible = context
        schema = self._schema_for(source, ingestible.nsweeps)
        edits = schema[ingestible.sweep].get(product)
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
        schema = self._schema_for(source, ingestible.nsweeps)
        edits = schema[ingestible.sweep].setdefault(product, Edits())
        edits.append(entry)
        self._persist(source, schema)

    def _latest_entry(self, product: str) -> tuple[bool, EditEntry]:
        if not self._active:
            return False, None
        context = self._current_context()
        if context is None:
            return False, None
        source, ingestible = context
        schema = self._schema_for(source, ingestible.nsweeps)
        edits = schema[ingestible.sweep].get(product)
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

    def _schema_for(self, source: Path, nsweeps: int) -> EditSchema:
        if self._source == source and self._schema is not None:
            return self._normalize_schema(self._schema, nsweeps)

        edit_path = self._edit_path(source)
        if edit_path.exists():
            with edit_path.open("rb") as stream:
                schema = pickle.load(stream)
            if not isinstance(schema, list):
                raise ValueError(f"Invalid edit schema in {edit_path}")
        else:
            schema = []

        schema = self._normalize_schema(schema, nsweeps)
        self._source = source
        self._schema = schema
        return schema

    @classmethod
    def _normalize_schema(cls, schema, nsweeps: int) -> EditSchema:
        if len(schema) < nsweeps:
            schema.extend({} for _ in range(nsweeps - len(schema)))
        elif len(schema) > nsweeps:
            del schema[nsweeps:]

        for sweep in schema:
            if not isinstance(sweep, dict):
                raise ValueError("Every edit-schema sweep must be a dictionary")
            for product, edits in tuple(sweep.items()):
                if isinstance(edits, Edits):
                    edits.index = min(
                        max(edits.index, -1),
                        len(edits.snapshots) - 1,
                    )
                else:
                    raise ValueError(
                        f"Product {product!r} has an invalid edit history"
                    )
        return schema

    def _persist(self, source: Path, schema: EditSchema):
        edit_path = self._edit_path(source)
        edit_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = edit_path.with_name(edit_path.name + ".tmp")
        with temporary.open("wb") as stream:
            pickle.dump(schema, stream, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(edit_path)
        self._source = source
        self._schema = schema

    @classmethod
    def _edit_directory(cls) -> Path:
        return Path.cwd() / cls.EDIT_DIRECTORY

    @classmethod
    def _edit_path(cls, source: Path) -> Path:
        return cls._edit_directory() / (source.name + cls.EDIT_SUFFIX)
