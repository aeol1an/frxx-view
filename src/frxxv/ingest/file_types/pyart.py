from ..file_ingestible import FileIngestible
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import numpy as np
import pyart

from frxxv.controllers.product_manager import ProductDefinition


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

    def get_product(self, name: str) -> ProductDefinition:
        attrs = deepcopy(self.data.fields[name])
        attrs.pop("data", None)
        return ProductDefinition(
            data=self.get_field(name).copy(),
            attrs=attrs,
        )

    def fieldAvail(self, name: str) -> bool:
        return name in self.data.fields

    def write_full_file(
        self,
        filename: Path | str,
        edit_history=None,
    ) -> None:
        output = deepcopy(self)
        if edit_history is not None:
            output._apply_edit_history(edit_history)
        output._write_file(filename)

    def write_sweeps(
        self,
        directory: Path | str,
        edit_history=None,
    ) -> tuple[Path, ...]:
        output = deepcopy(self)

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        instrument_name = output.instrumentName
        paths = []
        for sweep in range(output.nsweeps):
            sweep_time = output._sweep_datetime(sweep)
            datetime_string = (
                sweep_time.strftime("%Y%m%d_%H%M%S")
                + f".{sweep_time.microsecond // 1000:03d}"
            )
            path = directory / (
                f"cfrad.{instrument_name}.{datetime_string}.nc"
            )
            sweep_radar = output.data.extract_sweeps([sweep])
            if edit_history is not None:
                output._apply_sweep_edits(
                    sweep_radar,
                    edit_history[sweep],
                )
            pyart.io.write_cfradial(str(path), sweep_radar)
            paths.append(path)
        return tuple(paths)

    def _write_file(self, filename: Path | str) -> None:
        pyart.io.write_cfradial(str(filename), self.data)

    def _apply_edit_history(self, edit_history) -> None:
        products = {
            product
            for sweep_edits in edit_history
            for product in sweep_edits
        }
        recreations = {
            product
            for product in products
            if product in self.data.fields
            and bool(edit_history)
            and all(
                (edits := sweep_edits.get(product)) is not None
                and edits.recreates_variable()
                for sweep_edits in edit_history
            )
        }
        conflicts = sorted(
            product
            for product in products
            if product in self.data.fields
            and product not in recreations
            and not self._all_sweeps_deleted(product, edit_history)
            and any(
                edits.has_current and edits.definition() is not None
                for sweep_edits in edit_history
                if (edits := sweep_edits.get(product)) is not None
            )
        )
        if conflicts:
            names = ", ".join(repr(product) for product in conflicts)
            raise ValueError(
                f"New products are attempting to overwrite existing fields: "
                f"{names}. Explicitly delete the conflicting existing fields "
                "or remove/rename the new products before writing."
            )

        for product in products:
            active = [
                (sweep, edits)
                for sweep, sweep_edits in enumerate(edit_history)
                if (edits := sweep_edits.get(product)) is not None
                and edits.has_current
            ]
            if not active:
                continue

            if self._all_sweeps_deleted(product, edit_history):
                self.data.fields.pop(product, None)
                continue

            if product in recreations:
                self.data.fields.pop(product)

            definitions = [
                definition
                for _sweep, edits in active
                if (definition := edits.definition()) is not None
            ]
            if product not in self.data.fields:
                if not definitions:
                    raise ValueError(
                        f"Cannot write new product {product!r} without a "
                        "variable definition"
                    )
                self._create_field(product, definitions[-1])

            for sweep, edits in active:
                current = edits.current
                if current is None:
                    self._mask_sweep(product, sweep)
                    continue
                replacement = (
                    current["data"] if isinstance(current, dict) else current
                )
                self.data.fields[product]["data"][
                    self.data.get_slice(sweep)
                ] = replacement

    def _create_field(self, product: str, definition) -> None:
        attrs = deepcopy(definition.get("attrs", {}))
        source = np.asanyarray(definition["data"])
        data = np.ma.masked_all(
            (self.data.nrays, self.data.ngates),
            dtype=source.dtype,
        )
        if "_FillValue" in attrs:
            data.set_fill_value(attrs["_FillValue"])
        attrs["data"] = data
        self.data.fields[product] = attrs

    @staticmethod
    def _apply_sweep_edits(radar, sweep_edits) -> None:
        for product, edits in sweep_edits.items():
            if not edits.has_current:
                continue

            current = edits.current
            if current is None:
                radar.fields.pop(product, None)
                continue

            definition = edits.definition()
            replacement = (
                current["data"] if isinstance(current, dict) else current
            )
            if definition is not None:
                field = deepcopy(definition.get("attrs", {}))
                field["data"] = deepcopy(replacement)
                radar.fields[product] = field
                continue

            if product not in radar.fields:
                raise ValueError(
                    f"Cannot modify missing product {product!r} without a "
                    "variable definition"
                )
            radar.fields[product]["data"] = deepcopy(replacement)

    @staticmethod
    def _all_sweeps_deleted(product: str, edit_history) -> bool:
        return bool(edit_history) and all(
            (edits := sweep_edits.get(product)) is not None
            and edits.has_current
            and edits.current is None
            for sweep_edits in edit_history
        )

    def _mask_sweep(self, product: str, sweep: int) -> None:
        data = np.ma.array(self.data.fields[product]["data"], copy=False)
        data[self.data.get_slice(sweep)] = np.ma.masked
        self.data.fields[product]["data"] = data

    def _sweep_datetime(self, sweep: int, ray_index: int = 0):
        start = pyart.util.datetime_from_radar(self.data)
        sweep_start_ray = int(
            self.data.sweep_start_ray_index["data"][sweep]
        )
        sweep_end_ray = int(self.data.sweep_end_ray_index["data"][sweep])
        ray_count = sweep_end_ray - sweep_start_ray + 1
        if not 0 <= ray_index < ray_count:
            raise IndexError(
                f"Ray index {ray_index} is outside sweep {sweep}; "
                f"valid indices are 0 through {ray_count - 1}"
            )

        sweep_elapsed = float(
            self.data.time["data"][sweep_start_ray]
            - self.data.time["data"][0]
        )
        sweep_start = start + timedelta(seconds=sweep_elapsed)
        ray = sweep_start_ray + ray_index
        ray_elapsed = float(
            self.data.time["data"][ray]
            - self.data.time["data"][sweep_start_ray]
        )
        return sweep_start + timedelta(seconds=ray_elapsed)

    def constructTimeStr(self, ray_index: int = 0) -> str:
        self._validate_sweep()
        ray_time = self._sweep_datetime(self.sweep, ray_index)
        return ray_time.strftime("%m/%d/%Y %H:%M:%S Z")

    @property
    def instrumentName(self) -> str:
        return str(self.data.metadata.get("instrument_name", ""))

    @property
    def latitude(self) -> float:
        return float(np.asanyarray(self.data.latitude["data"]).reshape(-1)[0])

    @property
    def longitude(self) -> float:
        return float(np.asanyarray(self.data.longitude["data"]).reshape(-1)[0])

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
