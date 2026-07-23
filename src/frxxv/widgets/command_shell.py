"""A small application-command shell widget."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QFrame, QLineEdit, QPlainTextEdit, QVBoxLayout


class CommandShell(QFrame):
    """Display command output and collect Vim-style commands."""

    command_submitted = Signal(str)

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

        self.input = QLineEdit()
        self.input.setPlaceholderText(":command")
        self.input.setFont(fixed_font)
        self.input.returnPressed.connect(self._submit)
        layout.addWidget(self.input)

    def begin_command(self):
        """Prepare the input for a new Vim-style command."""
        self.input.setText(":")
        self.input.setCursorPosition(1)
        self.input.setFocus()

    def write(self, text: str):
        self.output.appendPlainText(text)

    def _submit(self):
        command = self.input.text()
        self.input.clear()
        self.command_submitted.emit(command)
