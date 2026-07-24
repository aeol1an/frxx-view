"""Panel-grid-wide aggregation of independent mask contributions."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject, Signal


class MaskController(QObject):
    """Combine named Boolean or integer masks for one data window."""

    update = Signal(str, object)
    changed = Signal(object)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._sources: dict[str, NDArray] = {}
        self._mask: NDArray[np.int32] | None = None
        self.update.connect(self._apply_update)

    @property
    def mask(self) -> NDArray[np.int32] | None:
        shape = self._data_shape()
        if shape is None:
            return None
        if self._mask is None or self._mask.shape != shape:
            self._mask = np.zeros(shape, dtype=np.int32)
            self._sources.clear()
        return self._mask.copy()

    def _apply_update(self, source: str, mask: NDArray):
        shape = self._data_shape()
        if shape is None:
            raise RuntimeError("Panel 0 has no data to define the mask shape")

        array = np.asarray(mask)
        if array.ndim != 2:
            raise ValueError("Panel-grid masks must be two-dimensional")
        if array.shape != shape:
            raise ValueError(
                f"Mask shape {array.shape} does not match "
                f"Panel 0 data shape {shape}"
            )
        if not (
            np.issubdtype(array.dtype, np.bool_)
            or np.issubdtype(array.dtype, np.integer)
        ):
            raise TypeError("Panel-grid masks must contain booleans or integers")
        if np.issubdtype(array.dtype, np.integer) and np.any(array < 0):
            raise ValueError("Mask contributions cannot be negative")

        contribution = array.astype(np.int32, copy=True)
        if self._mask is None or self._mask.shape != shape:
            self._mask = np.zeros(shape, dtype=np.int32)
            self._sources.clear()

        previous = self._sources.get(source)
        if previous is not None:
            self._mask -= previous.astype(np.int32, copy=False)
        if np.any(contribution):
            self._mask += contribution
            self._sources[source] = array.copy()
        else:
            self._sources.pop(source, None)
        self.changed.emit(self._mask.copy())

    def get(self, source: str) -> NDArray | None:
        """Return a copy of one engine's contribution."""
        mask = self._sources.get(source)
        return None if mask is None else mask.copy()

    def clear(self):
        """Remove all contributions when the active sweep changes."""
        self._sources.clear()
        shape = self._data_shape()
        self._mask = (
            None if shape is None else np.zeros(shape, dtype=np.int32)
        )
        if self._mask is not None:
            self.changed.emit(self._mask.copy())

    def _data_shape(self) -> tuple[int, int] | None:
        data = self.window.state.panels[0].data
        return None if data is None else data.shape
