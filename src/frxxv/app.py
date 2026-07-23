"""Application entry point."""
import sys
from importlib.resources import files
import setproctitle
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from frxxv.args import parse_args
from frxxv.config import LAYOUTS
from frxxv.controllers.file_manager import FileManager
from frxxv.ingest.case_types.directory import Directory
from frxxv.ingest.file_types.pyart import PyartFile
from frxxv.plotting.ppi import ppi_factory
from frxxv.state import AppState
from frxxv.windows.data_window import DataWindow

from frxx.utils.pathUtils import getPlatform


def main(argv=None):
    args = parse_args(argv)
    starting_directory = args.directory.expanduser().resolve()

    icon_path = str(Path(str(files("frxxv")/ '..' / '..' / "assets" / "frxx_icon.png")).resolve())

    sys.argv[0] = "Frxx View"
    app = QApplication([sys.argv[0]])

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

    # These objects belong to the application so every future window can
    # share the same case, file, sweep, and scan data.
    state = AppState()
    file_manager = FileManager(state, app)
    state.file_manager = file_manager

    if (starting_directory / "frxx_cases").is_dir():
        print("not implemented, treating as directory")
    case = Directory(starting_directory)
    file_manager.set_loader(PyartFile)


    window = DataWindow(
        "Frxx View",
        state=state,
        file_manager=file_manager,
    )

    fields = ["DBZ", "VEL", "ZDR", "RHOHV"]
    visible = len(LAYOUTS[state.layout])
    state.type = "ppi"
    for i in range(visible):
        panel = window.panel_grid.panels[i]
        panel.state.field_name = fields[i]
        panel.set_plot_factory(ppi_factory)

    file_manager.set_case(case, initial_index=args.filenum)

    window.show()
    sys.exit(app.exec())
