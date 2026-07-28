"""Write edited moment data as full files or one file per sweep."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from frxxv.config import USER_CONFIG
from frxxv.ingest.case_types.directory import Directory


COMMANDS = {"w", "write", "w!", "overwrite", "ws", "writesweeps"}


def execute(
    app_state,
    interaction_manager,
    shell_output: Any,
    action: str,
    *args: str,
):
    """Write the current file, routing validation and I/O errors to shell."""
    if args:
        shell_output.emit(f":{action} does not accept arguments", 1)
        return

    case = app_state.case
    if not isinstance(case, Directory):
        shell_output.emit(
            f":{action} is not implemented for {type(case).__name__} cases",
            1,
        )
        return

    source = case.current_file
    ingestible = case.data
    if source is None or ingestible is None:
        shell_output.emit("No file is currently loaded", 1)
        return

    try:
        edit_history = interaction_manager.window.edit_manager.edit_history
        if action in ("w!", "overwrite"):
            current_sweep = ingestible.sweep
            _overwrite(source, ingestible, edit_history)
            interaction_manager.window.edit_manager.clear_current_file_history()
            app_state.file_manager.reload_current(current_sweep)
            shell_output.emit(f"Overwrote {source}", 0)
            return

        output_directory = _output_directory(case)
        target = output_directory / source.name
        if target.exists():
            raise FileExistsError(
                f"Output already exists: {target}. Remove it explicitly "
                "before changing output formats or writing it again."
            )

        if action in ("ws", "writesweeps"):
            paths = ingestible.write_sweeps(target, edit_history)
            shell_output.emit(
                f"Wrote {len(paths)} sweep file(s) to {target}",
                0,
            )
            return

        output_directory.mkdir(parents=True, exist_ok=True)
        ingestible.write_full_file(target, edit_history)
        shell_output.emit(f"Wrote {target}", 0)
    except Exception as error:
        shell_output.emit(str(error), 1)


def _output_directory(case: Directory) -> Path:
    return case.directory / USER_CONFIG.user_config["outdir"]


def _overwrite(source: Path, ingestible, edit_history) -> None:
    if not ingestible.overwritable:
        raise PermissionError(
            f"{type(ingestible).__name__} does not allow source overwrites"
        )
    ingestible.write_full_file(source, edit_history)
