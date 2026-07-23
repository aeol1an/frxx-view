"""Parse and dispatch interactive shell commands."""
from __future__ import annotations

from dataclasses import dataclass
import shlex
from typing import Any

from frxxv.shell import nav, vals


class CommandParseError(ValueError):
    """Raised when shell input cannot be parsed into a command."""


@dataclass(frozen=True)
class ParsedCommand:
    """A normalized shell command and its arguments."""

    name: str
    args: tuple[str, ...]
    text: str


class ShellParser:
    """Parse regular commands and commands whose arguments may be attached."""

    ATTACHED_ARGUMENT_COMMANDS = ("+", "-", "n")

    def parse(self, raw_command: str) -> ParsedCommand:
        text = raw_command.strip()
        if text.startswith(":"):
            text = text[1:].strip()

        if not text:
            return ParsedCommand(name="", args=(), text="")

        for name in self.ATTACHED_ARGUMENT_COMMANDS:
            if text.startswith(name):
                return ParsedCommand(
                    name=name,
                    args=self._split(text[len(name):].strip()),
                    text=text,
                )

        tokens = self._split(text)
        return ParsedCommand(
            name=tokens[0],
            args=tokens[1:],
            text=text,
        )

    @staticmethod
    def _split(text: str) -> tuple[str, ...]:
        if not text:
            return ()
        try:
            return tuple(shlex.split(text))
        except ValueError as error:
            raise CommandParseError(str(error)) from error


PARSER = ShellParser()


def execute(app_state, shell_output: Any, raw_command: str) -> ParsedCommand | None:
    """Parse and dispatch a command, returning commands owned by the window."""
    try:
        command = PARSER.parse(raw_command)
    except CommandParseError as error:
        shell_output.emit(f"Could not parse command: {error}", 1)
        return None

    if command.name in ("+", "-"):
        direction = 1 if command.name == "+" else -1
        nav.execute(app_state, shell_output, direction, *command.args)
        return None

    if command.name in ("begin", "end"):
        nav.execute(app_state, shell_output, command.name, *command.args)
        return None

    if command.name == "n":
        nav.execute(app_state, shell_output, "n", *command.args)
        return None

    if command.name == "vals":
        vals.execute(app_state, shell_output, *command.args)
        return None

    # Window lifecycle commands remain owned by DataWindow.
    if command.name == "q":
        return command

    shell_output.emit(
        f"Not an editor command: {command.text or '<empty>'}",
        1,
    )
    return None
