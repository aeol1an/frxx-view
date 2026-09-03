import numpy as np
import numpy.typing as npt

def _rle_decode_core(
    comp_u16: npt.NDArray[np.uint16],
    comp_i16: npt.NDArray[np.int16],
    ngates: int,
) -> tuple[npt.NDArray[np.int16], int]: ...
