from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from ...file_ingestible import FileIngestible

from .dorade_reader import DoradeFile as DoradeReader


if TYPE_CHECKING:
    from frxxv.controllers.product_manager import ProductDefinition


_LIGHT_SPEED = 299_792_458.0


def _decode_text(value) -> str:
    return value.decode(errors="ignore").strip("\x00").strip()


class DoradeFile(FileIngestible):
    overwritable = True

    def __init__(self, filename, sweep=0):
        self.data: DoradeReader = DoradeReader(filename)
        self.products = sorted(self.data.data)
        self.nsweeps = 1
        self.sweep = sweep
        self._validate_sweep()

    def _validate_sweep(self):
        if self.sweep != 0:
            raise ValueError("DORADE sweep files contain exactly one sweep")

    def get_field(self, name):
        self._validate_sweep()
        return self.data.data[name]

    def get_product(self, name: str) -> ProductDefinition:
        from frxxv.controllers.product_manager import ProductDefinition

        parm = self.data.params[name]
        attrs = {
            "long_name": _decode_text(parm["param_description"]),
            "units": _decode_text(parm["param_units"]),
        }
        encoding = {
            "binary_format": parm["binary_format"],
            "parameter_scale": parm["parameter_scale"],
            "parameter_bias": parm["parameter_bias"],
            "bad_data": parm["bad_data"],
        }
        return ProductDefinition(
            data=self.get_field(name).copy(),
            attrs=attrs,
            encoding=encoding,
            dims=("ray", "range"),
        )

    def fieldAvail(self, name: str) -> bool:
        return name in self.data.data

    def write_full_file(
        self,
        filename: Path | str,
        edit_history=None,
    ) -> None:
        output = deepcopy(self.data)
        if edit_history is not None:
            self._apply_edit_history(output, edit_history)
        output.write(filename)

    def write_sweeps(
        self,
        directory: Path | str,
        edit_history=None,
    ) -> tuple[Path, ...]:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / self._sweep_filename()
        self.write_full_file(path, edit_history)
        return (path,)

    def _sweep_filename(self) -> str:
        timestamp = self._ray_datetime(0).strftime("%Y%m%d_%H%M%S.%f")[:-3]
        return f"swp.{self.instrumentName}.{timestamp}"

    @staticmethod
    def _apply_edit_history(output: DoradeReader, edit_history) -> None:
        if not edit_history:
            return
        if len(edit_history) != 1:
            raise ValueError("A DORADE file must have exactly one sweep of edits")

        for product, edits in edit_history[0].items():
            if not edits.has_current:
                continue
            current = edits.current
            if current is None:
                raise ValueError(
                    f"Removing DORADE product {product!r} is not supported"
                )
            if product not in output.data:
                raise ValueError(
                    f"Creating DORADE product {product!r} is not supported"
                )
            replacement = (
                current["data"] if isinstance(current, dict) else current
            )
            values = np.ma.asarray(replacement, dtype=np.float32).filled(np.nan)
            if values.shape != output.data[product].shape:
                raise ValueError(
                    f"Edited DORADE product {product!r} has shape "
                    f"{values.shape}; expected {output.data[product].shape}"
                )
            output.data[product][...] = values

    def _ray_datetime(self, ray_index: int = 0) -> datetime:
        if not 0 <= ray_index < len(self.data.rays):
            raise IndexError(
                f"Ray index {ray_index} is outside this sweep; valid indices "
                f"are 0 through {len(self.data.rays) - 1}"
            )
        ray = self.data.rays[ray_index]
        start = getattr(
            self.data,
            "sweep_start_time",
            getattr(self.data, "volume_datetime", None),
        )
        if start is None:
            raise LookupError("DORADE sweep time is unavailable")
        julian_day = int(ray["julian_day"])
        if julian_day > 0:
            date = datetime(start.year, 1, 1) + timedelta(days=julian_day - 1)
        else:
            date = datetime(start.year, start.month, start.day)
        return date + timedelta(
            hours=int(ray["hour"]),
            minutes=int(ray["minute"]),
            seconds=int(ray["second"]),
            milliseconds=int(ray["millisecond"]),
        )

    def constructTimeStr(self, ray_index: int = 0) -> str:
        self._validate_sweep()
        return self._ray_datetime(ray_index).strftime("%m/%d/%Y %H:%M:%S Z")

    @property
    def instrumentName(self) -> str:
        return self.data.instrument_name

    @property
    def latitude(self) -> float:
        return float(self.data.lat)

    @property
    def longitude(self) -> float:
        return float(self.data.lon)

    @property
    def rkm(self):
        if self.data.dist_cells is not None:
            return np.asarray(self.data.dist_cells, dtype=np.float32) / 1000.0
        if not self.products:
            raise LookupError("DORADE range information is unavailable")
        return np.asarray(
            self.data.get_sweep(self.products[0])["range"],
            dtype=np.float32,
        ) / 1000.0

    @property
    def az(self):
        self._validate_sweep()
        return np.asarray(
            [ray["azimuth"] for ray in self.data.rays],
            dtype=np.float32,
        )

    @property
    def el(self):
        self._validate_sweep()
        return np.asarray(
            [ray["elevation"] for ray in self.data.rays],
            dtype=np.float32,
        )

    @property
    def va(self):
        return np.asarray([self.data.nyquist_velocity], dtype=np.float32)

    @property
    def ra(self):
        return np.asarray(
            [self.data.unambiguous_range * 1000.0],
            dtype=np.float32,
        )

    @property
    def pw(self):
        pulse_lengths = {
            int(parm["pulse_width"])
            for parm in self.data.params.values()
            if int(parm["pulse_width"]) > 0
        }
        if not pulse_lengths:
            raise LookupError("DORADE pulse width is unavailable")
        return np.asarray(
            sorted(pulse_lengths),
            dtype=np.float64,
        ) / _LIGHT_SPEED

    @property
    def prt(self):
        values = [
            self.data._radd_prt1,
            self.data._radd_prt2,
            self.data._radd_prt3,
            self.data._radd_prt4,
            self.data._radd_prt5,
        ]
        count = max(int(self.data._radd_num_ipps), 1)
        values = [value for value in values[:count] if value > 0]
        if not values:
            return np.asarray(
                [2.0 * self.data.unambiguous_range * 1000.0 / _LIGHT_SPEED]
            )
        return np.asarray(values, dtype=np.float64) * 1e-6

    @property
    def wavelength(self):
        count = max(int(self.data._radd_num_freq), 1)
        frequencies = [
            getattr(self.data, f"_radd_freq{index}", 0.0)
            for index in range(1, min(count, 5) + 1)
        ]
        frequencies = [frequency for frequency in frequencies if frequency > 0]
        if not frequencies:
            return np.ascontiguousarray(4.0 * self.va * self.prt)
        return _LIGHT_SPEED / (
            np.asarray(frequencies, dtype=np.float64) * 1e9
        )

    @property
    def fixedAngle(self):
        self._validate_sweep()
        return self.data.fixed_angle

    def nextSweep(self) -> bool:
        return False

    def prevSweep(self) -> bool:
        return False

    def firstSweep(self):
        self.sweep = 0

    def lastSweep(self):
        self.sweep = 0
