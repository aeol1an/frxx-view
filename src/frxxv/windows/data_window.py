"""Top-level window for viewing and interacting with data."""
from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPauseAnimation,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Signal,
    Qt,
    QTimer,
)
from PySide6.QtGui import QActionGroup, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLayout,
    QMainWindow,
    QWidget,
    QVBoxLayout,
)

from frxxv.config import DEFAULT_LAYOUT, LAYOUTS
from frxxv.state import AppState
from frxxv.shell.shell import execute as execute_shell_command
from frxxv.shell.moments import execute as execute_moment_command
from frxxv.widgets.info_bar import InfoBar
from frxxv.widgets.panel_grid import PanelGrid
from frxxv.widgets.command_shell import CommandShell
from frxxv.controllers.interaction_manager import InteractionManager
from frxxv.controllers.key_router import (
    KeyRouter, ACTION_PREV_FILE, ACTION_NEXT_FILE,
)

class DataWindow(QMainWindow):
    shell_output = Signal(str, int)

    SHELL_ANIMATION_MS = 240
    SHELL_FADE_MS = 75
    SHELL_INSET_PX = 4

    def __init__(
        self,
        title: str,
        state: AppState,
        file_manager=None,
        shell_allowed: bool = True,
        shell_command_executor=execute_moment_command,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.shell_allowed = shell_allowed
        self.shell_command_executor = shell_command_executor

        # ── State ───────────────────────────────────────────────────
        self.state = state
        self.panel_double_clicked = self.state.panel_double_clicked
        self.plot_controller = self.state.plot_controller

        # ── Controllers ─────────────────────────────────────────────
        self.file_manager = (
            file_manager if file_manager is not None
            else self.state.file_manager
        )
        self.key_router   = KeyRouter(self.state)
        self.interactions = InteractionManager(self)

        # Wire file navigation into the key router
        self.key_router.register_global(
            ACTION_PREV_FILE, lambda: self.file_manager.navigate(-1))
        self.key_router.register_global(
            ACTION_NEXT_FILE, lambda: self.file_manager.navigate(1))

        # ── UI ──────────────────────────────────────────────────────
        self._build_menu_bar()
        self._build_central()
        self._shell_animation = None
        self._shell_close_size = None
        self._shell_close_queued = False

        self._shell_shortcut = None
        if self.shell_allowed:
            self._shell_shortcut = QShortcut(QKeySequence(":"), self)
            self._shell_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            self._shell_shortcut.activated.connect(self._show_shell)

        self.resize(512, 362)

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

        self._content_layout = QHBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)

        self._panel_grid_left_aligned = False
        self.panel_grid = PanelGrid(
            self.state,
            geometry_alignment_toggle=self._toggle_panel_grid_alignment,
        )
        self._content_layout.addWidget(self.panel_grid, stretch=1)

        self.shell_container = None
        self.shell = None
        self._shell_opacity = None
        self._shell_width_multiplier = 1
        self._shell_initial_target_width = 0
        self._shell_target_width = 0
        self._shell_resize_stretch_index = None
        if self.shell_allowed:
            self.shell_container = QWidget()
            shell_layout = QHBoxLayout(self.shell_container)
            shell_layout.setContentsMargins(self.SHELL_INSET_PX, 0, 0, 0)
            shell_layout.setSpacing(0)
            shell_layout.setSizeConstraint(
                QLayout.SizeConstraint.SetNoConstraint
            )

            self.shell = CommandShell()
            self.shell.command_submitted.connect(self._run_command)
            self.shell_output.connect(self.shell.write)
            shell_layout.addWidget(self.shell)

            self._shell_opacity = QGraphicsOpacityEffect(self.shell)
            self._shell_opacity.setOpacity(0.0)
            self.shell.setGraphicsEffect(self._shell_opacity)

            self._shell_initial_target_width = max(
                self.shell_container.sizeHint().width(),
                self.shell.minimumWidth() + self.SHELL_INSET_PX,
            )
            self._shell_target_width = self._shell_initial_target_width
            self.shell_container.setMinimumWidth(0)
            self.shell_container.setMaximumWidth(0)
            self.shell_container.hide()
            self._content_layout.addWidget(self.shell_container)
            self._content_layout.addStretch(0)
            self._shell_resize_stretch_index = self._content_layout.count() - 1

        vbox.addLayout(self._content_layout, stretch=1)

        self.setCentralWidget(central)

    def _toggle_panel_grid_alignment(self):
        self._panel_grid_left_aligned = not self._panel_grid_left_aligned
        alignment = (
            Qt.AlignmentFlag.AlignLeft
            if self._panel_grid_left_aligned
            else Qt.AlignmentFlag(0)
        )
        self._content_layout.setAlignment(self.panel_grid, alignment)

    # ── Command shell ───────────────────────────────────────────────

    def _show_shell(self):
        if self.shell is None or self.shell_container is None:
            return
        if self._shell_animation is not None:
            return
        if self.shell_container.isVisible():
            self.shell.input.setEnabled(True)
            self.shell.input.setFocus()
            return

        assert self.shell_container is not None
        assert self._shell_opacity is not None

        self.panel_grid.lock_geometry()
        self._content_layout.setStretchFactor(self.panel_grid, 0)
        self._content_layout.setStretchFactor(self.shell_container, 1)
        if self._shell_resize_stretch_index is not None:
            self._content_layout.setStretch(
                self._shell_resize_stretch_index,
                0,
            )

        self.shell.input.setEnabled(True)
        self._shell_opacity.setOpacity(0.0)
        self.shell_container.setMaximumWidth(0)
        self.shell_container.show()
        self.shell.begin_command()

        start_geometry = self.geometry()
        end_geometry = start_geometry.adjusted(
            0,
            0,
            self._shell_target_width,
            0,
        )

        geometry_animation = QPropertyAnimation(self, b"geometry")
        geometry_animation.setDuration(self.SHELL_ANIMATION_MS)
        geometry_animation.setStartValue(start_geometry)
        geometry_animation.setEndValue(end_geometry)
        geometry_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        width_animation = QPropertyAnimation(
            self.shell_container,
            b"maximumWidth",
        )
        width_animation.setDuration(self.SHELL_ANIMATION_MS)
        width_animation.setStartValue(0)
        width_animation.setEndValue(self._shell_target_width)
        width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        fade_animation = QPropertyAnimation(self._shell_opacity, b"opacity")
        fade_animation.setDuration(self.SHELL_FADE_MS)
        fade_animation.setStartValue(0.0)
        fade_animation.setEndValue(1.0)

        delayed_fade = QSequentialAnimationGroup()
        delayed_fade.addAnimation(
            QPauseAnimation(self.SHELL_ANIMATION_MS - self.SHELL_FADE_MS)
        )
        delayed_fade.addAnimation(fade_animation)

        animation = QParallelAnimationGroup(self)
        animation.addAnimation(geometry_animation)
        animation.addAnimation(width_animation)
        animation.addAnimation(delayed_fade)
        animation.finished.connect(self._finish_shell_open)
        self._shell_animation = animation
        animation.start()

    def _finish_shell_open(self):
        self._shell_animation = None
        assert self.shell_container is not None
        assert self._shell_opacity is not None
        self.shell_container.setFixedWidth(self._shell_target_width)
        self._shell_opacity.setOpacity(1.0)
        self._content_layout.setStretchFactor(self.shell_container, 0)
        self._content_layout.setStretchFactor(self.panel_grid, 1)
        self.panel_grid.unlock_geometry()
        if self._shell_close_queued:
            self._shell_close_queued = False
            self._hide_shell()

    def _hide_shell(self):
        if self.shell is None or self.shell_container is None:
            return
        if not self.shell_container.isVisible():
            return
        if self._shell_animation is not None:
            self._shell_close_queued = True
            self.shell.input.setEnabled(False)
            return

        self.panel_grid.lock_geometry()
        self._content_layout.setStretchFactor(self.panel_grid, 0)
        self._content_layout.setStretchFactor(self.shell_container, 1)
        if self._shell_resize_stretch_index is not None:
            self._content_layout.setStretch(
                self._shell_resize_stretch_index,
                0,
            )
        self.shell.input.setEnabled(False)
        self.shell_container.setMinimumWidth(0)

        start_geometry = self.geometry()
        visible_shell_width = self.shell_container.width()
        target_width = max(1, start_geometry.width() - self._shell_target_width)
        self._shell_close_size = (target_width, start_geometry.height())
        end_geometry = start_geometry.adjusted(
            0,
            0,
            -self._shell_target_width,
            0,
        )

        geometry_animation = QPropertyAnimation(self, b"geometry")
        geometry_animation.setDuration(self.SHELL_ANIMATION_MS)
        geometry_animation.setStartValue(start_geometry)
        geometry_animation.setEndValue(end_geometry)
        geometry_animation.setEasingCurve(QEasingCurve.Type.InCubic)

        width_animation = QPropertyAnimation(
            self.shell_container,
            b"maximumWidth",
        )
        width_animation.setDuration(self.SHELL_ANIMATION_MS)
        width_animation.setStartValue(visible_shell_width)
        width_animation.setEndValue(0)
        width_animation.setEasingCurve(QEasingCurve.Type.InCubic)

        fade_animation = QPropertyAnimation(self._shell_opacity, b"opacity")
        fade_animation.setDuration(self.SHELL_FADE_MS)
        fade_animation.setStartValue(1.0)
        fade_animation.setEndValue(0.0)

        animation = QParallelAnimationGroup(self)
        animation.addAnimation(geometry_animation)
        animation.addAnimation(width_animation)
        animation.addAnimation(fade_animation)
        animation.finished.connect(self._finish_shell_close)
        self._shell_animation = animation
        animation.start()

    def _finish_shell_close(self):
        self._shell_animation = None
        assert self.shell_container is not None
        assert self._shell_opacity is not None
        self.shell_container.hide()
        self.shell_container.setMaximumWidth(0)
        self._shell_opacity.setOpacity(0.0)
        self._content_layout.setStretchFactor(self.shell_container, 0)
        self._content_layout.setStretchFactor(self.panel_grid, 1)

        def finish_layout():
            if self._shell_close_size is not None:
                self.resize(*self._shell_close_size)
                self._shell_close_size = None
            self._shell_close_queued = False
            self.panel_grid.unlock_geometry()
            self.setFocus()

        QTimer.singleShot(10, finish_layout)

    def _resize_shell(self, multiplier_delta: int) -> bool:
        """Animate the visible shell by one initial-width increment."""
        if self.shell is None or self.shell_container is None:
            return False
        if not self.shell_container.isVisible() or self._shell_animation is not None:
            return False

        next_multiplier = max(1, self._shell_width_multiplier + multiplier_delta)
        if next_multiplier == self._shell_width_multiplier:
            return False

        next_width = self._shell_initial_target_width * next_multiplier
        width_delta = next_width - self._shell_target_width
        growing = width_delta > 0

        self.panel_grid.lock_geometry()
        self._content_layout.setStretchFactor(self.panel_grid, 0)
        assert self._shell_resize_stretch_index is not None
        if growing:
            self._content_layout.setStretchFactor(self.shell_container, 0)
            self._content_layout.setStretch(
                self._shell_resize_stretch_index,
                1,
            )
        else:
            self._content_layout.setStretchFactor(self.shell_container, 1)
            self._content_layout.setStretch(
                self._shell_resize_stretch_index,
                0,
            )
        self.shell.input.setEnabled(False)
        if not growing:
            self.shell_container.setMinimumWidth(0)

        start_geometry = self.geometry()
        end_geometry = start_geometry.adjusted(0, 0, width_delta, 0)

        geometry_animation = QPropertyAnimation(self, b"geometry")
        geometry_animation.setDuration(self.SHELL_ANIMATION_MS)
        geometry_animation.setStartValue(start_geometry)
        geometry_animation.setEndValue(end_geometry)
        geometry_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
            if width_delta > 0
            else QEasingCurve.Type.InCubic
        )

        width_animation = None
        if not growing:
            width_animation = QPropertyAnimation(
                self.shell_container,
                b"maximumWidth",
            )
            width_animation.setDuration(self.SHELL_ANIMATION_MS)
            width_animation.setStartValue(self.shell_container.width())
            width_animation.setEndValue(next_width)
            width_animation.setEasingCurve(QEasingCurve.Type.InCubic)

        self._shell_width_multiplier = next_multiplier
        self._shell_target_width = next_width

        animation = QParallelAnimationGroup(self)
        animation.addAnimation(geometry_animation)
        if width_animation is not None:
            animation.addAnimation(width_animation)
        animation.finished.connect(self._finish_shell_resize)
        self._shell_animation = animation
        animation.start()
        return True

    def _finish_shell_resize(self):
        self._shell_animation = None
        assert self.shell is not None
        assert self.shell_container is not None
        self.shell_container.setFixedWidth(self._shell_target_width)
        assert self._shell_resize_stretch_index is not None
        self._content_layout.setStretch(self._shell_resize_stretch_index, 0)
        self._content_layout.setStretchFactor(self.shell_container, 0)
        self._content_layout.setStretchFactor(self.panel_grid, 1)
        self.panel_grid.unlock_geometry()
        self.shell.input.setEnabled(True)
        self.shell.begin_command()

    def _run_command(self, raw_command: str):
        if self.shell is None:
            return

        command = execute_shell_command(
            self.state,
            self.interactions,
            self.shell_output,
            raw_command,
            self.shell_command_executor,
        )
        if command is not None and command.name == "q":
            self._hide_shell()
            return

        if command is not None and command.name in ("widen", "shrink"):
            if command.args:
                self.shell_output.emit(
                    f":{command.name} does not accept arguments",
                    self.shell.STDERR,
                )
            else:
                direction = 1 if command.name == "widen" else -1
                if self._resize_shell(direction):
                    return

        self.shell.begin_command()

    # ── Key routing ─────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if self.shell is not None and self.shell.input.hasFocus():
            if event.key() == Qt.Key.Key_Escape:
                self.panel_grid.take_keyboard_focus()
                event.accept()
                return
            super().keyPressEvent(event)
            return
        if not self.key_router.handle(event):
            super().keyPressEvent(event)
