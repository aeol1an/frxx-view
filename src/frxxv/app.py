"""
Application entry point.

    from frxxv.app import main
    main()              # empty panels
    main(demo=True)     # test figures
"""
import sys
from importlib.resources import files
import setproctitle

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from frxxv.windows.panel_window import PanelWindow
from frxxv.ingest.pyart import PyartData

import argparse

def main():

    icon_path = str(files("frxxv")/ '..' / '..' / "assets" / "frxx_icon.png")

    sys.argv[0] = "Frxx View"
    demo = "--demo" in sys.argv

    app = QApplication(sys.argv)

    setproctitle.setproctitle("Frxx View")

    try:
        from AppKit import NSApplication, NSImage  # type: ignore
        ns_app = NSApplication.sharedApplication()
        ns_app.setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(icon_path))
    except ImportError:
        pass

    app.setApplicationName("Frxx View")
    app.setApplicationDisplayName("Frxx View")

    app.setWindowIcon(QIcon(icon_path))

    window = PanelWindow("Frxx View")

    if demo:
        from frxxv.plotting.ppi import ppi_factory
        from frxxv.config import LAYOUTS

        fields = ["DBZ", "VEL", "ZDR", "RHOHV"]

        panels = window.panel_grid.panels
        visible = len(LAYOUTS[window.state.layout])
        data = PyartData("/Volumes/RadarData/frxx-dev/m.nc", sweep=0)
        window.state.scan_data = data
        window.state.type = "ppi"
        for i in range(visible):
            panels[i].state.field_name = fields[i]
            panels[i].set_plot_factory(ppi_factory)
            panels[i].replot()

    window.show()
    sys.exit(app.exec())

def open(app):
    print("hi")