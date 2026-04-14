"""
Top info bar: radar name (left) and scan time (right).
Refreshes reactively on AppState.scan_changed.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from frxxv.state import AppState


class InfoBar(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)

        self.radar_name_label = QLabel()
        self.radar_name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        lay.addWidget(self.radar_name_label)

        lay.addStretch()

        self.scan_time_label = QLabel()
        self.scan_time_label.setStyleSheet("font-size: 14px;")
        lay.addWidget(self.scan_time_label)

        self.state.scan_changed.connect(self._refresh)
        self._refresh()

    def _refresh(self):
        m = self.state.scan_metadata
        self.radar_name_label.setText(m.get("radar_name", ""))
        self.scan_time_label.setText(m.get("scan_time", ""))