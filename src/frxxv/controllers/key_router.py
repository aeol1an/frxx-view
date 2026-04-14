"""
Centralized keyboard routing.

GLOBAL_KEYS  — always handled (Escape, arrows, …)
PANEL_KEYS   — only when a panel is selected; changes that panel's field

Both are plain dicts — extend by adding entries.
"""
from __future__ import annotations

from typing import Callable, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from frxxv.state import AppState

# ── Action name constants ───────────────────────────────────────────
ACTION_DESELECT  = "deselect"
ACTION_PREV_FILE = "prev_file"
ACTION_NEXT_FILE = "next_file"

# ── Default key maps ────────────────────────────────────────────────
GLOBAL_KEYS: Dict[int, str] = {
    Qt.Key.Key_Escape: ACTION_DESELECT,
    Qt.Key.Key_Left:   ACTION_PREV_FILE,
    Qt.Key.Key_Right:  ACTION_NEXT_FILE,
}

PANEL_KEYS: Dict[int, str] = {
    # Extend per your data fields, e.g.:
    # Qt.Key.Key_R: "reflectivity",
    # Qt.Key.Key_V: "velocity",
}


class KeyRouter:
    def __init__(self, state: AppState):
        self.state = state
        self._global_handlers: Dict[str, Callable] = {
            ACTION_DESELECT: self._deselect,
        }

    # ── Public API ──────────────────────────────────────────────────

    def register_global(self, action: str, handler: Callable):
        """Register or replace a handler for a global action name."""
        self._global_handlers[action] = handler

    def handle(self, event: QKeyEvent) -> bool:
        """
        Route a key event.  Returns True if consumed, False otherwise.
        """
        key = event.key()

        # Global keys
        if key in GLOBAL_KEYS:
            action = GLOBAL_KEYS[key]
            handler = self._global_handlers.get(action)
            if handler is not None:
                handler()
            return True

        # Panel-scoped keys
        if key in PANEL_KEYS and self.state.selected is not None:
            field = PANEL_KEYS[key]
            idx = self.state.selected
            self.state.panels[idx].field_name = field
            self.state.panel_field_changed.emit(idx)
            return True

        return False

    # ── Built-in handlers ───────────────────────────────────────────

    def _deselect(self):
        self.state.selected = None