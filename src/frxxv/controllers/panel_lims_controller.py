from PySide6.QtCore import QObject, QTimer, Signal

from frxxv.config import RESIZE_DEBOUNCE_MS


class PanelLimsController(QObject):
    limits_changed = Signal(object, tuple, tuple)

    def __init__(self, interval_ms=RESIZE_DEBOUNCE_MS):
        super().__init__()

        self._updating = False
        self._registrations = {}
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

    def register_axes(self, receiver, canvas, ax):
        self.unregister_axes(receiver)
        sender = canvas

        xlim_callback = ax.callbacks.connect(
            "xlim_changed",
            lambda ax: self.request_update_from_axes(sender, ax)
        )

        ylim_callback = ax.callbacks.connect(
            "ylim_changed",
            lambda ax: self.request_update_from_axes(sender, ax)
        )

        limits_callback = (
            lambda changed_sender, xlim, ylim:
                self.apply_to(sender, changed_sender, ax, canvas, xlim, ylim)
        )
        self.limits_changed.connect(limits_callback)
        self._registrations[receiver] = (
            canvas,
            ax,
            xlim_callback,
            ylim_callback,
            limits_callback,
        )

    def unregister_axes(self, receiver):
        registration = self._registrations.pop(receiver, None)
        if registration is None:
            return

        canvas, ax, xlim_callback, ylim_callback, limits_callback = registration
        ax.callbacks.disconnect(xlim_callback)
        ax.callbacks.disconnect(ylim_callback)
        try:
            self.limits_changed.disconnect(limits_callback)
        except (RuntimeError, TypeError):
            pass

        if self._pending_sender is canvas:
            self._timer.stop()
            self._pending_sender = None
            self._pending_xlim = None
            self._pending_ylim = None
