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

from frxxv.config import USER_CONFIG
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

def _product_keys() -> Dict[int, str]:
    panel_keys: Dict[int, str] = {}
    products = USER_CONFIG.user_config["products"]

    for product, product_config in products.items():
        configured_key = product_config["key"]
        if len(configured_key) != 1 or not configured_key.isascii():
            raise ValueError(
                f"Product '{product}' key must be one ASCII character"
            )

        qt_key = ord(configured_key.upper())
        if qt_key in panel_keys:
            other_product = panel_keys[qt_key]
            raise ValueError(
                f"Products '{other_product}' and '{product}' both use "
                f"the key '{configured_key}'"
            )
        panel_keys[qt_key] = product

    return panel_keys


PANEL_KEYS = _product_keys()


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
            self.state.panels[idx].product_override = None
            self.state.panel_field_changed.emit(idx)
            return True

        return False

    # ── Built-in handlers ───────────────────────────────────────────

    def _deselect(self):
        self.state.selected = None
