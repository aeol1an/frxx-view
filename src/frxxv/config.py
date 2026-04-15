from math import sqrt

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
MIN_PANEL_HEIGHT_INCHES = 3. / sqrt(2)   # √2 ≈ 1.414 in

# ── Layouts ─────────────────────────────────────────────────────────
# Each entry is a list of (row, col, rowspan, colspan) per visible panel.
# Book order: left→right, top→bottom.
DEFAULT_LAYOUT = "1x1"
LAYOUTS = {
    "1x1": [(0, 0, 1, 1)],
    "1x2": [(0, 0, 1, 1), (0, 1, 1, 1)],
    "2x1": [(0, 0, 1, 1), (1, 0, 1, 1)],
    "2x2": [(0, 0, 1, 1), (0, 1, 1, 1),
            (1, 0, 1, 1), (1, 1, 1, 1)],
}
NUM_PANELS = 4  # total persistent panels (book pages)

# ── Timing ──────────────────────────────────────────────────────────
RESIZE_DEBOUNCE_MS      = 0
DEFAULT_POLL_INTERVAL_MS = 2000