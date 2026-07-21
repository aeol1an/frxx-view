from math import sqrt
from copy import deepcopy

import platformdirs as pd
from pathlib import Path
import frxx.utils.pathUtils as pu
import frxx.viz.defaultPlotParameters as dpp
import json

"""
Central configuration constants.
All magic numbers live here so they're easy to find and change.
"""

# ── Appearance ──────────────────────────────────────────────────────
BORDER_COLOR_UNSELECTED = "#8E8E93"   # Apple space grey
BORDER_COLOR_SELECTED   = "#93C5FD"   # Pale blue
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

class ConfigManager():
    default_config = {
        "DEFAULT_LAYOUT": "2x2",

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
                "cmap": dpp.moments["ZDR"]["cmap"],
            },
            "RHOHV": {
                "priority": ["RHOHV", "correlation_coefficient"],
                "key": "r",
                "units": dpp.moments["RHOHV"]["units"],
                "clims": dpp.moments["RHOHV"]["ranges"],
                "cmap": dpp.moments["RHOHV"]["cmap"],
            }
        }
    }

    # "*" permits any product name while still restricting the keys that
    # may appear inside each product's configuration.
    config_schema = {
        "DEFAULT_LAYOUT": str,
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

    def __init__(self):
        self.user_config = deepcopy(self.default_config)
        self.config_path = Path(pd.user_config_dir("frxx"))/"frxxv.json"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        if self.config_path.exists() and self.config_path.stat().st_size > 0:
            with open(self.config_path, "r") as f:
                self.config_files = json.load(f)
        else:
            self.config_files = []
            with open(self.config_path, "w") as f:
                json.dump(self.config_files, f)

        for file in self.config_files:
            config_path = pu.jsonToPath(file)
            with config_path.open("r") as f:
                override = json.load(f)

            if not isinstance(override, dict):
                raise TypeError(f"Config file must contain an object: {config_path}")
            self._merge_config(
                self.user_config,
                override,
                self.config_schema,
                config_path,
            )

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
