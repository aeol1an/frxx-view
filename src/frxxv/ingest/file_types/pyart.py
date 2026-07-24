from ..file_ingestible import FileIngestible
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import numpy as np
import pyart


_LIGHT_SPEED = 299_792_458.0


class PyartFile(FileIngestible):
    overwritable = False

    def __init__(self, filename, sweep=0):
        self.data: pyart.core.Radar = pyart.io.read(filename)
        self.products = sorted(self.data.fields)
        self.nsweeps = self.data.nsweeps
        self.sweep = sweep
        self._validate_sweep()

    def _validate_sweep(self):
        if not 0 <= self.sweep < self.nsweeps:
            raise ValueError(
                f"Invalid sweep {self.sweep}. "
                f"Valid range is 0 to {self.nsweeps - 1}."
            )

    def get_field(self, name):
        self._validate_sweep()
        return self.data.get_field(self.sweep, name)

    def get_product(self, name: str):
        product = deepcopy(self.data.fields[name])
        product["data"] = self.get_field(name).copy()
        return product

    def fieldAvail(self, name: str) -> bool:
        return name in self.data.fields

    def write(self, filename: Path | str) -> None:
        pyart.io.write_cfradial(str(filename), self.data)

    def constructTimeStr(self) -> str:
        self._validate_sweep()
        start = pyart.util.datetime_from_radar(self.data)
        ray = int(self.data.sweep_start_ray_index["data"][self.sweep])
        elapsed = float(
            self.data.time["data"][ray] - self.data.time["data"][0]
        )
        sweep_time = start + timedelta(seconds=elapsed)
        return sweep_time.strftime("%m/%d/%Y %H:%M:%S Z")

    @property
    def instrumentName(self) -> str:
        return str(self.data.metadata.get("instrument_name", ""))

    @property
    def rkm(self):
        return self.data.range["data"] / 1000.0

    @property
    def az(self):
        self._validate_sweep()
        return self.data.get_azimuth(self.sweep)

    @property
    def el(self):
        self._validate_sweep()
        return self.data.get_elevation(self.sweep)

    @property
    def va(self):
        values = self._parameter("nyquist_velocity")
        if values is not None:
            return values
        wavelength = self._direct_wavelength()
        if wavelength is None:
            raise LookupError("Nyquist velocity unavailable")
        return np.ascontiguousarray(wavelength / (4.0 * self.prt))

    @property
    def ra(self):
        values = self._parameter("unambiguous_range")
        if values is not None:
            return values
        return np.ascontiguousarray(_LIGHT_SPEED * self.prt / 2.0)

    @property
    def pw(self):
        values = self._parameter("pulse_width")
        if values is None:
            raise LookupError("Pulse width unavailable")
        return values

    @property
    def prt(self):
        values = self._parameter("prt")
        if values is not None:
            return values
        max_range = self._parameter("unambiguous_range")
        if max_range is None:
            raise LookupError("Pulse repetition time unavailable")
        return np.ascontiguousarray(2.0 * max_range / _LIGHT_SPEED)

    @property
    def wavelength(self):
        values = self._direct_wavelength()
        if values is not None:
            return values
        nyquist = self._parameter("nyquist_velocity")
        if nyquist is None:
            raise LookupError("Radar wavelength unavailable")
        return np.ascontiguousarray(4.0 * nyquist * self.prt)

    @property
    def fixedAngle(self):
        self._validate_sweep()
        return self.data.fixed_angle["data"][self.sweep]

    def _parameter(self, name):
        """Return direct Py-ART metadata, selecting this sweep if ray based."""
        self._validate_sweep()
        parameters = self.data.instrument_parameters or {}
        if name not in parameters:
            return None
        values = np.asanyarray(parameters[name]["data"])
        if values.ndim and len(values) == self.data.nrays:
            values = values[self.data.get_slice(self.sweep)]
        elif values.ndim and len(values) == self.nsweeps:
            values = values[self.sweep:self.sweep + 1]
        return np.ascontiguousarray(np.atleast_1d(values))

    def _direct_wavelength(self):
        for name in ("wavelength", "radar_wavelength"):
            values = self._parameter(name)
            if values is not None:
                return values

        frequency = self._parameter("frequency")
        if frequency is not None:
            return np.ascontiguousarray(_LIGHT_SPEED / frequency)

        metadata_wavelength = self.data.metadata.get("wavelength")
        if metadata_wavelength is None:
            return None
        return np.ascontiguousarray(np.atleast_1d(metadata_wavelength))

    def nextSweep(self) -> bool:
        if self.sweep >= self.nsweeps - 1:
            return False
        self.sweep += 1
        return True

    def prevSweep(self) -> bool:
        if self.sweep <= 0:
            return False
        self.sweep -= 1
        return True

    def firstSweep(self):
        self.sweep = 0

    def lastSweep(self):
        self.sweep = self.nsweeps - 1
