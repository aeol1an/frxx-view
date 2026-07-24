"""Resolve configured product names into complete plotting specifications."""
from __future__ import annotations

from frxxv.config import USER_CONFIG
from frxxv.ingest.file_ingestible import FileIngestible
from frxxv.state import ProductSpec


def resolve_registered_product(
    data: FileIngestible,
    requested: str,
) -> ProductSpec | None:
    """Resolve a configured name or alias against one ingestible file."""
    requested_key = requested.casefold()
    available = set(data.products or ())

    for title, config in USER_CONFIG.user_config["products"].items():
        aliases = config["priority"]
        if requested_key != title.casefold() and not any(
            requested_key == alias.casefold() for alias in aliases
        ):
            continue

        raw_field = next(
            (alias for alias in aliases if alias in available),
            None,
        )
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

    return None
