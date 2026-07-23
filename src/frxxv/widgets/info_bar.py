"""Top bar showing instrument, scan time, and target angle."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from frxxv.state import AppState


class InfoBar(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)

        self.instrument_name_label = QLabel()
        self.instrument_name_label.setStyleSheet(
            "font-weight: bold; font-size: 14px;"
        )
        lay.addWidget(self.instrument_name_label)

        lay.addStretch()

        self.scan_time_label = QLabel()
        self.scan_time_label.setStyleSheet("font-size: 14px;")
        lay.addWidget(self.scan_time_label)

        lay.addStretch()

        self.target_angle_label = QLabel()
        self.target_angle_label.setStyleSheet("font-size: 14px;")
        lay.addWidget(self.target_angle_label)

        self.state.scan_changed.connect(self._refresh)
        self._refresh()

    def _refresh(self):
        m = self.state.scan_metadata
        self.instrument_name_label.setText(m.get("instrument_name", ""))
        self.scan_time_label.setText(m.get("scan_time", ""))
        self.target_angle_label.setText(m.get("target_angle", ""))
