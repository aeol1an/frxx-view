"""Built-in commands for non-wrapping file navigation."""
from __future__ import annotations

from typing import Any


def execute(
    app_state,
    shell_output: Any,
    action: int | str,
    *args: str,
):
    """Navigate by a sweep count or jump to a case boundary."""
    if action in ("begin", "end"):
        _go_to_boundary(app_state, shell_output, action, args)
        return
    if action == "n":
        _go_to_file(app_state, shell_output, args)
        return

    if len(args) > 1:
        shell_output.emit("Navigation accepts at most one sweep count", 1)
        return

    try:
        count = int(args[0]) if args else 1
    except ValueError:
        shell_output.emit("Navigation sweep count must be an integer", 1)
        return

    if count < 0:
        shell_output.emit("Navigation sweep count cannot be negative", 1)
        return

    case = app_state.case
    if not case.files:
        shell_output.emit("Navigation halted: the case has no files", 1)
        return

    direction = int(action)
    halted = app_state.file_manager.navigate(direction * count)
    if halted:
        boundary = "end" if direction > 0 else "beginning"
        shell_output.emit(
            f"Navigation halted at the {boundary} of the case",
            1,
        )


def _go_to_boundary(app_state, shell_output: Any, boundary: str, args):
    if args:
        shell_output.emit(f":{boundary} does not accept arguments", 1)
        return

    case = app_state.case
    if not case.files:
        shell_output.emit("Navigation halted: the case has no files", 1)
        return

    if boundary == "begin":
        app_state.file_manager.load_file(0)
    else:
        app_state.file_manager.load_file(
            len(case.files) - 1,
            last_sweep=True,
        )


def _go_to_file(app_state, shell_output: Any, args):
    if len(args) != 1:
        shell_output.emit(":n requires one file number", 1)
        return

    try:
        file_number = int(args[0])
    except ValueError:
        shell_output.emit(":n file number must be an integer", 1)
        return

    case = app_state.case
    if file_number < 0 or file_number >= len(case.files):
        shell_output.emit(
            f"File number {file_number} is out of range "
            f"for a case with {len(case.files)} files",
            1,
        )
        return

    app_state.file_manager.load_file(file_number)
