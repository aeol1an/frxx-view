from .frxxv_ingestible import FrxxvIngestible
import pyart


class PyartData(FrxxvIngestible):
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

    def nextSweepAvail(self) -> bool:
        return self.sweep < self.nsweeps - 1

    def prevSweepAvail(self) -> bool:
        return self.sweep > 0