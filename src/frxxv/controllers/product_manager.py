"""Window-scoped resolution of configured, edited, and source products."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import numpy as np

from frxxv.config import USER_CONFIG
from frxxv.state import ProductSpec


_MISSING = object()


@dataclass(frozen=True)
class ResolvedProduct:
    raw_field: str
    data: Any
    title: str
    cmap: str
    vmin: float
    vmax: float
    nticks: int
    units: str


class ProductManager:
    """Choose effective product data for one data window."""

    def __init__(self, window):
        self.window = window

    def select_registered(self, requested: str) -> ProductSpec | None:
        """Build a registered specification for the first known priority."""
        configured = self._registered_config(requested)
        if configured is None:
            return None
        title, config = configured
        raw_field = self._first_priority_name(config["priority"])
        if raw_field is None:
            return None
        vmin, vmax, nticks = config["clims"]
        return ProductSpec(
            raw_field=raw_field,
            title=title,
            cmap=config["cmap"],
            vmin=float(vmin),
            vmax=float(vmax),
            nticks=int(nticks),
            units=config["units"],
            registered_name=title,
        )

    def resolve(self, product: ProductSpec | None) -> ResolvedProduct | None:
        """Resolve a specification against edits first, then source data."""
        if product is None:
            return None

        if product.registered_name is None:
            data = self._candidate_data(product.raw_field)
            if data is _MISSING:
                data = self._empty_sweep()
                if data is None:
                    return None
            raw_field = product.raw_field
        else:
            configured = self._registered_config(product.registered_name)
            if configured is None:
                return None
            _title, config = configured
            raw_field = self._first_priority_name(config["priority"])
            if raw_field is None:
                raw_field = product.raw_field
            data = self._candidate_data(raw_field)
            if data is _MISSING:
                data = self._empty_sweep()
                if data is None:
                    return None

        return ResolvedProduct(
            raw_field=raw_field,
            data=data,
            title=product.title,
            cmap=product.cmap,
            vmin=product.vmin,
            vmax=product.vmax,
            nticks=product.nticks,
            units=product.units,
        )

    def available_products(self) -> list[str]:
        """List every raw product addressable by product navigation."""
        return self._known_product_names()

    def resolve_raw(self, requested: str) -> tuple[str, Any] | None:
        """Resolve one known raw product name case-insensitively."""
        requested_key = requested.casefold()
        raw_field = next(
            (
                name
                for name in self._known_product_names()
                if name.casefold() == requested_key
            ),
            None,
        )
        if raw_field is None:
            return None
        data = self._candidate_data(raw_field)
        if data is _MISSING:
            data = self._empty_sweep()
            if data is None:
                return None
        return raw_field, data

    def full_product(self, requested: str) -> tuple[str, dict[str, Any]] | None:
        """Resolve a raw product and return a complete editable definition."""
        resolved = self.resolve_raw(requested)
        if resolved is None:
            return None
        raw_field, effective_data = resolved

        found, edit = self.window.edit_manager.current_entry(raw_field)
        if found and isinstance(edit, dict):
            product = deepcopy(edit)
        else:
            product = self.window.edit_manager.product_definition(raw_field)
            ingestible = self.window.state.scan_data
            if product is None:
                if (
                    ingestible is not None
                    and raw_field in (ingestible.products or ())
                ):
                    product = ingestible.get_product(raw_field)
                else:
                    product = {}
        product["data"] = deepcopy(effective_data)
        return raw_field, product

    def _first_priority_name(self, priorities) -> str | None:
        """Return the first known product in configured priority order."""
        known = {
            name.casefold(): name
            for name in self._known_product_names()
        }
        return next(
            (
                known[raw_field.casefold()]
                for raw_field in priorities
                if raw_field.casefold() in known
            ),
            None,
        )

    def _known_product_names(self) -> list[str]:
        """List source and edit-history names, regardless of edit cursor."""
        ingestible = self.window.state.scan_data
        if ingestible is None:
            return []
        names = set(ingestible.products or ())
        names.update(self.window.edit_manager.product_names())
        return sorted(names)

    def _candidate_data(self, raw_field: str):
        found, edit = self.window.edit_manager.current_entry(raw_field)
        if found:
            if edit is None:
                return _MISSING
            if isinstance(edit, dict):
                if "data" not in edit:
                    raise ValueError(
                        f"Edited product {raw_field!r} has no 'data' member"
                    )
                return edit["data"]
            return edit

        ingestible = self.window.state.scan_data
        if ingestible is None or raw_field not in (ingestible.products or ()):
            return _MISSING
        return ingestible[raw_field]

    def _empty_sweep(self):
        """Return an all-NaN field matching the current sweep geometry."""
        ingestible = self.window.state.scan_data
        if ingestible is None:
            return None
        return np.full(
            (len(ingestible.az), len(ingestible.rkm)),
            np.nan,
            dtype=float,
        )

    @staticmethod
    def _registered_config(requested: str):
        requested_key = requested.casefold()
        for title, config in USER_CONFIG.user_config["products"].items():
            aliases = config["priority"]
            if requested_key == title.casefold() or any(
                requested_key == alias.casefold() for alias in aliases
            ):
                return title, config
        return None
