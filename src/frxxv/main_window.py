"""
Main application window.

Assembles menu bar, info bar, and panel grid.
Owns the key router and file manager.
"""
from PySide6.QtGui import QActionGroup, QKeyEvent
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout

from frxxv.config import DEFAULT_LAYOUT, LAYOUTS
from frxxv.state import AppState
from frxxv.widgets.info_bar import InfoBar
from frxxv.widgets.panel_grid import PanelGrid
from frxxv.controllers.key_router import (
    KeyRouter, ACTION_PREV_FILE, ACTION_NEXT_FILE,
)
from frxxv.controllers.file_manager import FileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Frxx View")

        # ── State ───────────────────────────────────────────────────
        self.state = AppState(self)

        # ── Controllers ─────────────────────────────────────────────
        self.file_manager = FileManager(self.state, self)
        self.key_router   = KeyRouter(self.state)

        # Wire file navigation into the key router
        self.key_router.register_global(
            ACTION_PREV_FILE, lambda: self.file_manager.navigate(-1))
        self.key_router.register_global(
            ACTION_NEXT_FILE, lambda: self.file_manager.navigate(1))

        # ── UI ──────────────────────────────────────────────────────
        self._build_menu_bar()
        self._build_central()

        self.resize(1024, 768)

    # ── Menu bar ────────────────────────────────────────────────────

    def _build_menu_bar(self):
        mb = self.menuBar()

        # View → Layout
        view_menu   = mb.addMenu("&View")
        layout_menu = view_menu.addMenu("Layout")

        group = QActionGroup(self)
        group.setExclusive(True)

        for key in LAYOUTS:
            label  = key.replace("x", "×")
            action = layout_menu.addAction(label)
            action.setCheckable(True)
            action.setActionGroup(group)
            action.setData(key)
            if key == DEFAULT_LAYOUT:
                action.setChecked(True)
            action.triggered.connect(
                lambda _checked, k=key: self._set_layout(k))

        # Easy to add more menus here:
        # mb.addMenu("&File")
        # mb.addMenu("&Tools")

    def _set_layout(self, key: str):
        self.state.layout = key

    # ── Central widget ──────────────────────────────────────────────

    def _build_central(self):
        central = QWidget()
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        self.info_bar = InfoBar(self.state)
        vbox.addWidget(self.info_bar)

        self.panel_grid = PanelGrid(self.state)
        vbox.addWidget(self.panel_grid, stretch=1)

        self.setCentralWidget(central)

    # ── Key routing ─────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if not self.key_router.handle(event):
            super().keyPressEvent(event)