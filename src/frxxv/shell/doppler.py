"""Display unique Doppler acquisition parameters for the current sweep."""
from __future__ import annotations

from typing import Any

import numpy as np


COMMANDS = {
    "va": ("Nyquist velocity", "va", 1.0, "m/s"),
    "nyquist": ("Nyquist velocity", "va", 1.0, "m/s"),
    "ra": ("Unambiguous range", "ra", 1e-3, "km"),
    "maxrange": ("Unambiguous range", "ra", 1e-3, "km"),
    "pw": ("Pulse width", "pw", 1e6, "µs"),
    "pulsewidth": ("Pulse width", "pw", 1e6, "µs"),
    "wl": ("Wavelength", "wavelength", 1.0, "m"),
    "wavelength": ("Wavelength", "wavelength", 1.0, "m"),
    "prt": ("PRT", "prt", 1.0, "s"),
    "prf": ("PRF", "prf", 1.0, "Hz"),
}


def execute(
    app_state,
    interaction_manager,
    shell_output: Any,
    action: str,
    *args: str,
):
    """Print the unique values of one current-sweep Doppler parameter."""
    del interaction_manager
    if args:
        shell_output.emit(f":{action} does not accept arguments", 1)
        return

    ingestible = app_state.scan_data
    if ingestible is None:
        shell_output.emit("No file is currently loaded", 1)
        return

    label, attribute, scale, units = COMMANDS[action]
    try:
        if attribute == "prf":
            prt = np.asanyarray(ingestible.prt)
            values = np.divide(
                1.0,
                prt,
                out=np.full(prt.shape, np.nan, dtype=float),
                where=prt != 0,
            )
        else:
            values = getattr(ingestible, attribute)
    except (AttributeError, KeyError, LookupError, TypeError, ValueError) as error:
        shell_output.emit(str(error), 1)
        return

    unique = np.unique(np.asanyarray(values) * scale)
    shell_output.emit(
        f"{label} ({units}): {np.array2string(unique, separator=', ')}",
        0,
    )
