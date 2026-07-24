from ..file_ingestible import FileIngestible
from datetime import timedelta

import pyart


class PyartFile(FileIngestible):
    def __init__(self, filename, sweep=0):
        self.radar: pyart.core.Radar = pyart.io.read(filename)
        self.nsweeps = self.radar.nsweeps
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
        return self.radar.get_field(self.sweep, name)

    def fieldAvail(self, name: str) -> bool:
        return name in self.radar.fields

    def products(self) -> list[str]:
        return sorted(self.radar.fields)

    def constructTimeStr(self) -> str:
        self._validate_sweep()
        start = pyart.util.datetime_from_radar(self.radar)
        ray = int(self.radar.sweep_start_ray_index["data"][self.sweep])
        elapsed = float(
            self.radar.time["data"][ray] - self.radar.time["data"][0]
        )
        sweep_time = start + timedelta(seconds=elapsed)
        return sweep_time.strftime("%m/%d/%Y %H:%M:%S Z")

    @property
    def instrumentName(self) -> str:
        return str(self.radar.metadata.get("instrument_name", ""))

    @property
    def rkm(self):
        return self.radar.range["data"] / 1000.0

    @property
    def az(self):
        self._validate_sweep()
        return self.radar.get_azimuth(self.sweep)

    @property
    def el(self):
        self._validate_sweep()
        return self.radar.get_elevation(self.sweep)

    @property
    def fixedAngle(self):
        self._validate_sweep()
        return self.radar.fixed_angle["data"][self.sweep]

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
