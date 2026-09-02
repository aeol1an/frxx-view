from math import sqrt
from copy import deepcopy

import platformdirs as pd
from pathlib import Path
import frxx.utils.pathUtils as pu
import frxx.viz.defaultPlotParameters as dpp
import json
from matplotlib import colormaps
import sys

"""
Central configuration constants.
All magic numbers live here so they're easy to find and change.
"""


def _named_colormap(name, cmap):
    """Register a custom default colormap and return its config-safe name."""
    if name not in colormaps:
        if isinstance(cmap, str):
            cmap = colormaps[cmap]
        colormaps.register(cmap, name=name)
    return name

# ── Appearance ──────────────────────────────────────────────────────
BORDER_COLOR_UNSELECTED = "#8E8E93"   # Apple space grey
BORDER_COLOR_SELECTED   = "#93C5FD"   # Pale blue
BACKGROUND_COLOR        = "#323232"
FOREGROUND_COLOR        = "#FFFFFF"
TITLE_BAR_COLOR         = "#383938"
TITLE_BAR_TEXT_COLOR    = "#B5B5B4"
BORDER_WIDTH_PX  = 2
BORDER_RADIUS_PX = 4

# ── Panel sizing ────────────────────────────────────────────────────
MIN_PANEL_WIDTH_INCHES  = 3.
MIN_PANEL_HEIGHT_INCHES = MIN_PANEL_WIDTH_INCHES / sqrt(2)   # √2 ≈ 1.414 in

# ── Layouts ─────────────────────────────────────────────────────────
# Each entry is a list of (row, col, rowspan, colspan) per visible panel.
# Book order: left→right, top→bottom.
LAYOUTS = {
    "1x1": [(0, 0, 1, 1)],
    "1x2": [(0, 0, 1, 1), (0, 1, 1, 1)],
    "2x1": [(0, 0, 1, 1), (1, 0, 1, 1)],
    "2x2": [(0, 0, 1, 1), (0, 1, 1, 1),
            (1, 0, 1, 1), (1, 1, 1, 1)],
}
NUM_PANELS = 4  # total persistent panels (book pages)

# ── Timing ──────────────────────────────────────────────────────────
RESIZE_DEBOUNCE_MS      = 100
DEFAULT_POLL_INTERVAL_MS = 2000

class ConfigManager:
    default_config = {
        "DEFAULT_LAYOUT": "2x2",
        "outdir": "frxxv_output",
        "device_pixel_ratio": 2.0,
        "initial_products": ["DBZ", "VEL", "ZDR", "RHOHV"],

        "products": {
            "DBZ": {
                "priority": ["DBZ", "REF", "reflectivity"],
                "key": "z",
                "units": dpp.moments["DBZ"]["units"],
                "clims": dpp.moments["DBZ"]["ranges"],
                "cmap": dpp.moments["DBZ"]["cmap"],
            },
            "VEL": {
                "priority": ["VC", "CORVEL", "VEL", "velocity"],
                "key": "v",
                "units": dpp.moments["VEL"]["units"],
                "clims": dpp.moments["VEL"]["ranges"],
                "cmap": dpp.moments["VEL"]["cmap"],
            },
            "ZDR": {
                "priority": ["ZDR", "differential_reflectivity"],
                "key": "d",
                "units": dpp.moments["ZDR"]["units"],
                "clims": dpp.moments["ZDR"]["ranges"],
                "cmap": _named_colormap(
                    "frxxdmap",
                    dpp.moments["ZDR"]["cmap"],
                ),
            },
            "RHOHV": {
                "priority": ["RHOHV", "correlation_coefficient"],
                "key": "r",
                "units": dpp.moments["RHOHV"]["units"],
                "clims": dpp.moments["RHOHV"]["ranges"],
                "cmap": _named_colormap(
                    "frxxrmap",
                    dpp.moments["RHOHV"]["cmap"],
                ),
            },
            "WIDTH": {
                "priority": ["WIDTH", "spectrum_width"],
                "key": "w",
                "units": dpp.moments["WIDTH"]["units"],
                "clims": dpp.moments["WIDTH"]["ranges"],
                "cmap": dpp.moments["WIDTH"]["cmap"],
            }
        }
    }

    # "*" permits any product name while still restricting the keys that
    # may appear inside each product's configuration.
    config_schema = {
        "DEFAULT_LAYOUT": str,
        "outdir": str,
        "device_pixel_ratio": float,
        "initial_products": list,
        "products": {
            "*": {
                "priority": list,
                "key": str,
                "units": str,
                "clims": list,
                "cmap": str,
            }
        },
    }

    def __init__(self, config_path: Path | None = None):
        self.user_config = deepcopy(self.default_config)
        self.config_path = config_path or (
            Path(pd.user_config_dir("frxx")) / "frxxv.json"
        )
        self.config_files = self._load_config_files()
        self._load_overrides()

    def _load_config_files(self) -> list:
        """Load the ordered override path list, falling back to no overrides."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.config_path.exists() or self.config_path.stat().st_size == 0:
                self._write_config_files([])
                return []
            with self.config_path.open("r") as config_file:
                config_files = json.load(config_file)
            if not isinstance(config_files, list):
                raise TypeError(
                    f"Config index must contain a list: {self.config_path}"
                )
            return config_files
        except Exception as error:
            self._report_error("Could not load config index", error)
            return []

    def _load_overrides(self):
        """Apply valid absolute-path overrides in their listed order."""
        for encoded_path in self.config_files:
            try:
                config_path = pu.jsonToPath(encoded_path)
            except Exception as error:
                self._report_error("Invalid config path", error)
                continue
            self.apply_config(config_path)

    def apply_config(self, config_path: Path) -> bool:
        """Atomically apply one absolute config override."""
        try:
            if not config_path.is_absolute():
                raise ValueError(f"Config path must be absolute: {config_path}")
            with config_path.open("r") as config_file:
                override = json.load(config_file)
            if not isinstance(override, dict):
                raise TypeError(
                    f"Config file must contain an object: {config_path}"
                )

            merged = deepcopy(self.user_config)
            self._merge_config(
                merged,
                override,
                self.config_schema,
                config_path,
            )
        except Exception as error:
            self._report_error(f"Could not load config {config_path}", error)
            return False

        self.user_config = merged
        return True

    def add_config(self, config_path: Path):
        """Append an absolute config-file path to the override index."""
        config_path = config_path.expanduser().resolve()
        if not config_path.is_file():
            raise FileNotFoundError(f"Config file does not exist: {config_path}")
        encoded_path = pu.pathToJson(config_path)
        self.config_files.append(encoded_path)
        self._write_config_files(self.config_files)

    def remove_config(self, config_path: Path):
        """Remove one absolute config-file path from the override index."""
        config_path = config_path.expanduser().resolve()
        encoded_path = pu.pathToJson(config_path)
        try:
            self.config_files.remove(encoded_path)
        except ValueError as error:
            raise ValueError(
                f"Config path is not registered: {config_path}"
            ) from error
        self._write_config_files(self.config_files)

    def _write_config_files(self, config_files: list):
        """Write the ordered override path list to the config index."""
        with self.config_path.open("w") as config_file:
            json.dump(config_files, config_file, indent=2)
            config_file.write("\n")

    @staticmethod
    def _report_error(context, error):
        print(f"{context}: {type(error).__name__}: {error}", file=sys.stderr)

    @classmethod
    def _merge_config(cls, dest, src, schema, config_path, key_path=""):
        for key, value in src.items():
            value_schema = schema.get(key, schema.get("*"))
            current_path = f"{key_path}.{key}" if key_path else key

            if value_schema is None:
                raise KeyError(
                    f"Unknown config key '{current_path}' in {config_path}"
                )

            if isinstance(value_schema, dict):
                if not isinstance(value, dict):
                    raise TypeError(
                        f"Config value '{current_path}' in {config_path} "
                        "must be an object"
                    )
                if key not in dest or not isinstance(dest[key], dict):
                    dest[key] = {}
                cls._merge_config(
                    dest[key],
                    value,
                    value_schema,
                    config_path,
                    current_path,
                )
                continue

            if not isinstance(value, value_schema):
                raise TypeError(
                    f"Invalid value for '{current_path}' in {config_path}; "
                    f"expected {value_schema.__name__}"
                )

            # Scalars and lists replace the previous value wholesale.
            dest[key] = deepcopy(value)


    

USER_CONFIG = ConfigManager()
DEFAULT_LAYOUT = USER_CONFIG.user_config["DEFAULT_LAYOUT"]

# TODO(config): validate required product fields and setting semantics; support
# removing inherited products, live reload, and runtime refresh of snapshotted
# settings such as DEFAULT_LAYOUT, keyboard mappings, and panel DPI.
