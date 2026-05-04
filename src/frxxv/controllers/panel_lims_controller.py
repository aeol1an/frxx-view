from PySide6.QtCore import QObject, QTimer, Signal

from frxxv.config import RESIZE_DEBOUNCE_MS


class PanelLimsController(QObject):
    limits_changed = Signal(object, tuple, tuple)

    def __init__(self, interval_ms=RESIZE_DEBOUNCE_MS):
        super().__init__()

        self._updating = False
        self._pending_sender = None
        self._pending_xlim = None
        self._pending_ylim = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._flush)

    def request_update_from_axes(self, sender, ax):
        if self._updating:
            return

        self._pending_sender = sender
        self._pending_xlim = ax.get_xlim()
        self._pending_ylim = ax.get_ylim()

        if not self._timer.isActive():
            self._timer.start()

    def _flush(self):
        sender = self._pending_sender
        xlim = self._pending_xlim
        ylim = self._pending_ylim

        if sender is None:
            return

        self.limits_changed.emit(sender, xlim, ylim)

    def apply_to(self, receiver, sender, ax, canvas, xlim, ylim):
        if receiver is sender:
            return

        self._updating = True
        try:
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            canvas.draw_idle()
        finally:
            self._updating = False

    def register_axes(self, canvas, ax):
        sender = canvas

        ax.callbacks.connect(
            "xlim_changed",
            lambda ax: self.request_update_from_axes(sender, ax)
        )

        ax.callbacks.connect(
            "ylim_changed",
            lambda ax: self.request_update_from_axes(sender, ax)
        )

        self.limits_changed.connect(
            lambda changed_sender, xlim, ylim:
                self.apply_to(sender, changed_sender, ax, canvas, xlim, ylim)
        )