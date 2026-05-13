"""
Application entry point.

    from frxxv.app import main
    main()              # empty panels
    main(demo=True)     # test figures
"""
import sys
from importlib.resources import files
import setproctitle
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from frxxv.windows.panel_window import PanelWindow
from frxxv.ingest.file_types.pyart import PyartFile

from frxx.utils.pathUtils import getPlatform

import argparse

def main():

    icon_path = str(Path(str(files("frxxv")/ '..' / '..' / "assets" / "frxx_icon.png")).resolve())

    sys.argv[0] = "Frxx View"
    demo = "--demo" in sys.argv

    app = QApplication(sys.argv)

    setproctitle.setproctitle("Frxx View")

    platform = getPlatform()
    if platform == "macos":
        try:
            from AppKit import NSApplication, NSImage  # type: ignore
            ns_app = NSApplication.sharedApplication()
            ns_app.setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(icon_path))
        except ImportError:
            pass
    elif platform == "linux":
        apps_dir = Path.home() / ".local/share/applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = apps_dir/"frxx-view.desktop"
        desktop_file.write_text(
            f"[Desktop Entry]\n"
            f"Name=Frxx View\n"
            f"Exec=true\n"
            f"Icon={icon_path}\n"
            f"Type=Application\n"
            f"NoDisplay=true"
            f"Terminal=false\n"
        )
        app.setDesktopFileName('frxx-view')

        
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
        #data = PyartFile("/run/media/aeolian/RadarData/frxx-dev/m.nc", sweep=0)
        data = PyartFile("/Volumes/RadarData2/frxx-dev/m.nc", sweep=0)
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