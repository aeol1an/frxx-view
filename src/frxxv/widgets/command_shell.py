"""A small application-command shell widget."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QKeyEvent,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QFrame, QLineEdit, QPlainTextEdit, QVBoxLayout


class HistoryLineEdit(QLineEdit):
    """Single-line command editor with terminal-style history traversal."""

    HISTORY_LIMIT = 500

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._history_index = 0
        self._draft = ""

    def remember(self, command: str):
        """Store a non-empty command and reset history traversal."""
        if command.strip().lstrip(":").strip():
            self._history.append(command)
            if len(self._history) > self.HISTORY_LIMIT:
                del self._history[:-self.HISTORY_LIMIT]
        self.reset_history_navigation()

    def reset_history_navigation(self):
        self._history_index = len(self._history)
        self._draft = self.text()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Up:
            self._show_previous_command()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down:
            self._show_next_command()
            event.accept()
            return
        super().keyPressEvent(event)

    def _show_previous_command(self):
        if not self._history:
            return
        if self._history_index == len(self._history):
            self._draft = self.text()
        if self._history_index > 0:
            self._history_index -= 1
        self._set_command(self._history[self._history_index])

    def _show_next_command(self):
        if self._history_index >= len(self._history):
            return
        self._history_index += 1
        command = (
            self._draft
            if self._history_index == len(self._history)
            else self._history[self._history_index]
        )
        self._set_command(command)

    def _set_command(self, command: str):
        self.setText(command)
        self.setCursorPosition(len(command))


class CommandShell(QFrame):
    """Display command output and collect Vim-style commands."""

    command_submitted = Signal(str)
    STDOUT = 0
    STDERR = 1
    OUTPUT_COLORS = {
        STDOUT: QColor("#F2F2F7"),
        STDERR: QColor("#FFD60A"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("command_shell")
        self.setMinimumWidth(260)
        self.setStyleSheet(
            "QFrame#command_shell {"
            "  background-color: #1E1E1E;"
            "  border: 1px solid #8E8E93;"
            "  border-radius: 4px;"
            "}"
            "QPlainTextEdit, QLineEdit {"
            "  background-color: #1E1E1E;"
            "  color: #F2F2F7;"
            "  border: none;"
            "}"
        )

        fixed_font = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Command output")
        self.output.setFont(fixed_font)
        layout.addWidget(self.output, stretch=1)

        self.input = HistoryLineEdit()
        self.input.setPlaceholderText(":command")
        self.input.setFont(fixed_font)
        self.input.returnPressed.connect(self._submit)
        layout.addWidget(self.input)

    def begin_command(self):
        """Prepare the input for a new Vim-style command."""
        self.input.setText(":")
        self.input.setCursorPosition(1)
        self.input.reset_history_navigation()
        self.input.setFocus()

    def write(self, text: str, stream: int = STDOUT):
        """Append output using the color assigned to the given stream."""
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if not self.output.document().isEmpty():
            cursor.insertBlock()

        text_format = QTextCharFormat()
        text_format.setForeground(
            self.OUTPUT_COLORS.get(stream, self.OUTPUT_COLORS[self.STDOUT])
        )
        cursor.insertText(str(text), text_format)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _submit(self):
        command = self.input.text()
        self.input.remember(command)
        self.input.clear()
        self.command_submitted.emit(command)
