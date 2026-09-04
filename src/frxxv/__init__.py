"""frxx_view — a PySide6 radar data viewer."""

import os
os.environ['PYART_QUIET'] = 'true'

from . import pcolormesh

__all__ = ["pcolormesh"]
