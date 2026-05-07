from math import sqrt

import platformdirs as pd
from pathlib import Path
import frxx.utils.pathUtils as pu
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

def traverse(src, dest=None, target_key=None, func=lambda x: x):
    if dest is None:
        dest = src

    if isinstance(src, dict) and isinstance(dest, dict):
        for key in src:
            if target_key is None or key == target_key:
                dest[key] = func(src[key])
                if isinstance(src[key], (dict, list)):
                    traverse(src[key], dest[key], target_key, func)
            else:
                # Recurse into dest in parallel with src
                dest_child = dest.get(key, src[key]) if isinstance(dest, dict) else src[key]
                traverse(src[key], dest_child, target_key, func)
    elif isinstance(src, list) and isinstance(dest, list):
        for i, item in enumerate(src):
            if isinstance(dest, list) and i < len(dest):
                traverse(item, dest[i], target_key, func)
            else:
                traverse(item, item, target_key, func)

    return dest

class ConfigManager():
    user_config = {
        "DEFAULT_LAYOUT": "2x2",

        "products": {
            "DBZ": {
                "priority": ["DBZ", "REF", "reflectivity"],
                "key": "z"
            },
            "VEL": {
                "priority": ["VC", "CORVEL", "VEL", "velocity"],
                "key": "v"
            },
            "ZDR": {
                "priority": ["ZDR", "differential_reflectivity"],
                "key": "d"
            },
            "RHOHV": {
                "priority": ["RHOHV", "correlation_coefficient"],
                "key": "r"
            }
        }
    }

    def __init__(self):
        self.config_path = Path(pd.user_config_dir("frxx"))/"frxxv.json"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        if self.config_path.exists() and self.config_path.stat().st_size > 0:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        else:
            self.config_files = []
            with open(self.config_path, "w") as f:
                json.dump(self.config_files, f)

        with open(self.config_path, "r") as f:
            self.config_files = json.load(f)

        for file in self.config_files:
            config_path = pu.jsonToPath(file)


    

USER_CONFIG = ConfigManager()
DEFAULT_LAYOUT = USER_CONFIG.user_config["DEFAULT_LAYOUT"]