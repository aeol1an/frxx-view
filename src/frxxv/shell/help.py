"""Display concise help for interactive shell commands."""
from __future__ import annotations

from typing import Any


COMMANDS = {
    "Command shell": {
        "cmds": (
            (
                ":help",
                "list available commands",
                'Usage:\n'
                '  :help [COMMAND]\n'
                '\n'
                'Lists all commands when COMMAND is omitted. If COMMAND is '
                'provided, shows detailed help for that command.',
            ),
            (
                ":q",
                "close the command shell",
                'Usage:\n'
                '  :q\n'
                '\n'
                'Closes the command shell without closing the data window.',
            ),
            (
                ":widen",
                "make the command shell wider",
                'Usage:\n'
                '  :widen\n'
                '\n'
                'Widens the command shell by one step.',
            ),
            (
                ":shrink",
                "make the command shell narrower",
                'Usage:\n'
                '  :shrink\n'
                '\n'
                'Narrows the command shell by one step.',
            ),
        ),
        "data_window_type": "all",
    },
    "Navigation": {
        "cmds": (
            (
                ":+",
                "move forward by sweeps",
                'Usage:\n'
                '  :+ [NUMSWEEPS]\n'
                '\n'
                'Moves forward by NUMSWEEPS without wrapping past the end of '
                'the case. NUMSWEEPS is an optional nonnegative integer that '
                'defaults to 1. The space before NUMSWEEPS may be omitted.',
            ),
            (
                ":-",
                "move backward by sweeps",
                'Usage:\n'
                '  :- [NUMSWEEPS]\n'
                '\n'
                'Moves backward by NUMSWEEPS without wrapping past the start '
                'of the case. NUMSWEEPS is an optional nonnegative integer '
                'that defaults to 1. The space before NUMSWEEPS may be '
                'omitted.',
            ),
            (
                ":n",
                "show or select the case file number",
                'Usage:\n'
                '  :n [FILENUM]\n'
                '\n'
                'Shows the current file number when FILENUM is omitted, or '
                'loads zero-based file number FILENUM when provided. The '
                'space before FILENUM may be omitted.',
            ),
            (
                ":begin",
                "go to the first sweep in the case",
                'Usage:\n'
                '  :begin\n'
                '\n'
                'Loads the first file and first sweep in the case.',
            ),
            (
                ":end",
                "go to the last sweep in the case",
                'Usage:\n'
                '  :end\n'
                '\n'
                'Loads the last file and last sweep in the case.',
            ),
            (
                ":ls",
                "list case files",
                'Usage:\n'
                '  :ls\n'
                '\n'
                'Lists every file in the case with its zero-based file '
                'number. An asterisk marks the current file.',
            ),
            (
                ":le",
                "list case files with active edits",
                'Usage:\n'
                '  :le\n'
                '\n'
                'Lists case files that have active edit histories. An '
                'asterisk marks the current file.',
            ),
        ),
        "data_window_type": "moments",
    },
    "Products": {
        "cmds": (
            (
                ":lp",
                "list products in the current file",
                'Usage:\n'
                '  :lp\n'
                '\n'
                'Lists the FIELD names available in the current file, '
                'including fields created through active edits.',
            ),
            (
                ":lock",
                "lock the selected panel to its current raw field",
                'Usage:\n'
                '  :lock\n'
                '\n'
                'Changes the selected panel from a configured search product '
                'to its currently resolved FIELD. The panel then remains on '
                'that field instead of following configured priorities.',
            ),
            (
                ":p",
                "set the selected panel's product",
                'Usage:\n'
                '  :p SEARCH_PROD\n'
                '  :p FIELD SHORTHAND CMAP\n'
                '  :p FIELD SHORTHAND CMAP VMIN VMAX\n'
                '  :p FIELD SHORTHAND CMAP VMIN VMAX NTICKS\n'
                '  :p FIELD SHORTHAND CMAP VMIN VMAX NTICKS UNITS\n'
                '\n'
                'SEARCH_PROD selects the first available field using its '
                'priority order in the product configuration. FIELD is the '
                'product name in the file itself, and SHORTHAND is the plot '
                'title. Custom VMIN and VMAX may both be empty strings to '
                'calculate fixed limits from the current data. NTICKS '
                'defaults to 5. With one optional trailing '
                'argument, an integer is NTICKS; any other value is UNITS. '
                'Fields not present in the current data require explicit '
                'VMIN and VMAX.',
            ),
        ),
        "data_window_type": "all",
    },
    "Doppler information": {
        "cmds": (
            (
                ":prf",
                "show pulse repetition frequency",
                'Usage:\n'
                '  :prf\n'
                '\n'
                'Prints the unique pulse repetition frequencies for the '
                'current sweep in hertz.',
            ),
            (
                ":prt",
                "show pulse repetition time",
                'Usage:\n'
                '  :prt\n'
                '\n'
                'Prints the unique pulse repetition times for the current '
                'sweep in seconds.',
            ),
            (
                ":pw, :pulsewidth",
                "show pulse width",
                'Usage:\n'
                '  :pw\n'
                '  :pulsewidth\n'
                '\n'
                'Prints the unique pulse widths for the current sweep in '
                'microseconds. The two commands are aliases.',
            ),
            (
                ":ra, :maxrange",
                "show unambiguous range",
                'Usage:\n'
                '  :ra\n'
                '  :maxrange\n'
                '\n'
                'Prints the unique unambiguous ranges for the current sweep '
                'in kilometers. The two commands are aliases.',
            ),
            (
                ":wl, :wavelength",
                "show radar wavelength",
                'Usage:\n'
                '  :wl\n'
                '  :wavelength\n'
                '\n'
                'Prints the unique radar wavelengths for the current sweep '
                'in meters. The two commands are aliases.',
            ),
            (
                ":va, :nyquist",
                "show Nyquist velocity",
                'Usage:\n'
                '  :va\n'
                '  :nyquist\n'
                '\n'
                'Prints the unique Nyquist velocities for the current sweep '
                'in meters per second. The two commands are aliases.',
            ),
        ),
        "data_window_type": "all",
    },
    "Double-click tools": {
        "cmds": (
            (
                ":vals",
                "toggle moment-value output and click marker",
                'Usage:\n'
                '  :vals\n'
                '\n'
                'Enables or disables printing gate and moment values when a '
                'panel is double-clicked. The selected gate is marked on all '
                'panels.',
            ),
            (
                ":center",
                "toggle plot centering",
                'Usage:\n'
                '  :center\n'
                '\n'
                'Enables or disables recentering the plots on a '
                'double-clicked gate while preserving the current zoom.',
            ),
            (
                ":coords",
                "toggle latitude/longitude output",
                'Usage:\n'
                '  :coords\n'
                '\n'
                'Enables or disables printing the latitude and longitude of '
                'a double-clicked gate.',
            ),
            (
                ":raytime",
                "toggle ray-time output",
                'Usage:\n'
                '  :raytime\n'
                '\n'
                'Enables or disables printing the timestamp of the ray '
                'containing a double-clicked gate.',
            ),
        ),
        "data_window_type": "moments",
    },
    "Product editing": {
        "cmds": (
            (
                ":copy",
                "copy a product in the current sweep",
                'Usage:\n'
                '  :copy SOURCE_FIELD DEST_FIELD\n'
                '\n'
                'Copies SOURCE_FIELD to a new DEST_FIELD in the current '
                'sweep. Both arguments are required, and FIELD names refer to '
                'products in the file itself.',
            ),
            (
                ":copyall",
                "copy a product across all sweeps in file",
                'Usage:\n'
                '  :copyall SOURCE_FIELD DEST_FIELD\n'
                '\n'
                'Copies SOURCE_FIELD to a new DEST_FIELD in every sweep of '
                'the current file. Both arguments are required, and FIELD '
                'names refer to products in the file itself.',
            ),
            (
                ":del",
                "delete a product in the current sweep",
                'Usage:\n'
                '  :del FIELD\n'
                '\n'
                'Marks FIELD for deletion in the current sweep. FIELD is the '
                'product name in the file itself.',
            ),
            (
                ":delall",
                "delete a product across all sweeps in file",
                'Usage:\n'
                '  :delall FIELD\n'
                '\n'
                'Marks FIELD for deletion in every sweep of the current file. '
                'FIELD is the product name in the file itself.',
            ),
        ),
        "data_window_type": "all",
    },
    "Value editing": {
        "cmds": (
            (
                ":set",
                "set selected gates in the selected product",
                'Usage:\n'
                '  :set VALUE\n'
                '\n'
                'Sets every gate in the current selection mask to the '
                'floating-point VALUE in the selected panel\'s field. VALUE '
                'is required.',
            ),
        ),
        "data_window_type": "all",
    },
    "Edit history": {
        "cmds": (
            (
                ":edits",
                "list edits in the current sweep",
                'Usage:\n'
                '  :edits\n'
                '\n'
                'Lists each edited FIELD and its history in the current '
                'sweep. An asterisk marks the active history state.',
            ),
            (
                ":sedits, :sweepedits",
                "list edits in the current sweep",
                'Usage:\n'
                '  :sedits\n'
                '  :sweepedits\n'
                '\n'
                'Lists each edited FIELD and its history in the current '
                'sweep. An asterisk marks the active history state. The two '
                'commands are aliases of :edits.',
            ),
            (
                ":pedits",
                "list a product's edits across all sweeps in file",
                'Usage:\n'
                '  :pedits [FIELD]\n'
                '\n'
                'Lists the edit history for FIELD in every sweep of the '
                'current file. FIELD is optional and defaults to the selected '
                'panel\'s field.',
            ),
            (
                ":undo",
                "undo one current-sweep product edit",
                'Usage:\n'
                '  :undo [FIELD]\n'
                '\n'
                'Moves FIELD back one edit in the current sweep. FIELD is '
                'optional and defaults to the selected panel\'s field.',
            ),
            (
                ":undoall",
                "undo one product edit across all sweeps",
                'Usage:\n'
                '  :undoall [FIELD]\n'
                '\n'
                'Moves FIELD back one edit in every sweep of the current '
                'file. FIELD is optional and defaults to the selected panel\'s '
                'field.',
            ),
            (
                ":redo",
                "redo one current-sweep product edit",
                'Usage:\n'
                '  :redo [FIELD]\n'
                '\n'
                'Moves FIELD forward one edit in the current sweep. FIELD is '
                'optional and defaults to the selected panel\'s field.',
            ),
            (
                ":redoall",
                "redo one product edit across all sweeps in file",
                'Usage:\n'
                '  :redoall [FIELD]\n'
                '\n'
                'Moves FIELD forward one edit in every sweep of the current '
                'file. FIELD is optional and defaults to the selected panel\'s '
                'field.',
            ),
            (
                ":rmedits",
                "remove a product's current-sweep edit history",
                'Usage:\n'
                '  :rmedits FIELD\n'
                '\n'
                'Removes the entire edit history for FIELD from the current '
                'sweep. FIELD is required.',
            ),
        ),
        "data_window_type": "all",
    },
    "Selections": {
        "cmds": (
            (
                ":bnd",
                "toggle interactive boundary drawing",
                'Usage:\n'
                '  :bnd\n'
                '\n'
                'Enables or disables boundary selection. Double-click to add '
                'boundary points, then Shift+double-click after at least '
                'three points to close the boundary and update the selection '
                'mask.',
            ),
            (
                ":mask",
                "toggle display of the combined selection mask",
                'Usage:\n'
                '  :mask\n'
                '\n'
                'Enables or disables hiding gates outside the combined '
                'selection mask on every panel. This changes only the display.',
            ),
        ),
        "data_window_type": "all",
    },
    "Moment Value Editing": {
        "cmds": (
            (
                ":fu, :forced_unfolding",
                "force-unfold selected velocities",
                'Usage:\n'
                '  :fu FOLD_COUNT\n'
                '  :forced_unfolding FOLD_COUNT\n'
                '\n'
                'Force-unfolds selected gates in the selected panel\'s '
                'velocity field into the interval centered on integer '
                'FOLD_COUNT times the Nyquist velocity. FOLD_COUNT is '
                'required. The two commands are aliases.',
            ),
        ),
        "data_window_type": "moments",
    },
    "Figure export": {
        "cmds": (
            (
                ":savefig",
                "save visible panels as a PNG",
                'Usage:\n'
                '  :savefig [NAME [AZIMUTH_INTERVAL [RANGE_INTERVAL]]]\n'
                '\n'
                'Saves the visible panels as a 300 DPI PNG in the configured '
                'output image directory. NAME defaults to the current file '
                'name. AZIMUTH_INTERVAL and RANGE_INTERVAL default to 60 and '
                '3; either grid can be disabled by passing None for its '
                'interval. Optional arguments are positional, so NAME is '
                'required when either interval is provided.',
            ),
        ),
        "data_window_type": "moments",
    },
    "File output": {
        "cmds": (
            (
                ":w, :write",
                "write the edited current file",
                'Usage:\n'
                '  :w\n'
                '  :write\n'
                '\n'
                'Writes the current file with active edits to the configured '
                'output directory. It refuses to replace an existing output '
                'file. The two commands are aliases.',
            ),
            (
                ":w!, :overwrite",
                "overwrite the current file with its edits",
                'Usage:\n'
                '  :w!\n'
                '  :overwrite\n'
                '\n'
                'Overwrites the source file with active edits, clears that '
                'file\'s edit history, and reloads the current sweep. The file '
                'format must support overwriting. The two commands are '
                'aliases.',
            ),
            (
                ":ws, :writesweeps",
                "write one edited file per sweep",
                'Usage:\n'
                '  :ws\n'
                '  :writesweeps\n'
                '\n'
                'Writes the current file with active edits as one output file '
                'per sweep in the configured output directory. It refuses to '
                'replace an existing output target. The two commands are '
                'aliases.',
            ),
        ),
        "data_window_type": "moments",
    },
}


def detailed_help(requested: str) -> str | None:
    """Return detailed help for a command when it has been documented."""
    requested = requested.removeprefix(":").casefold()
    for section in COMMANDS.values():
        for command in section["cmds"]:
            aliases = (
                alias.strip().removeprefix(":").casefold()
                for alias in command[0].split(",")
            )
            if requested in aliases:
                return command[2] if len(command) == 3 else None
    return None


def execute(shell_output: Any, *args: str):
    """List the commands understood by the interactive shell."""
    if args:
        if len(args) > 1:
            shell_output.emit(":help accepts at most one command", 1)
            return
        command_help = detailed_help(args[0])
        if command_help is None:
            requested = args[0].removeprefix(":")
            shell_output.emit(f"No help found for :{requested}", 1)
            return
        shell_output.emit(command_help, 0)
        return

    lines = ["Available commands:"]
    for title, section in COMMANDS.items():
        lines.extend(("", f"{title}:"))
        for command, description, *_details in section["cmds"]:
            lines.extend((f"  {command}", f"    {description}"))
    lines.extend(
        (
            "",
            "Use :help COMMAND for detailed help.",
        )
    )
    shell_output.emit("\n".join(lines), 0)
