"""Application entry point."""
import sys
import setproctitle
from importlib import resources
from pathlib import Path
from shutil import copyfile

from frxxv.args import handle_config_action, parse_args


def main(argv=None):
    args = parse_args(argv)
    if handle_config_action(args):
        return

    from frxxv import config as app_config
    from frxxv import pcolormesh

    if args.config is not None:
        temporary_config = args.config.expanduser().resolve()
        app_config.USER_CONFIG.apply_config(temporary_config)
        app_config.DEFAULT_LAYOUT = app_config.USER_CONFIG.user_config[
            "DEFAULT_LAYOUT"
        ]

    pcolormesh.install()
    starting_directory = args.directory.expanduser().resolve()

    icon = resources.files("frxxv").joinpath("assets", "frxx_icon.png")
    with resources.as_file(icon) as icon_path:
        _run_app(args, starting_directory, str(icon_path))


def _run_app(args, starting_directory, icon_path):
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from frxx.utils.pathUtils import getPlatform
    from frxxv.state import AppState

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
        icons_dir = Path.home() / ".local/share/icons"
        icons_dir.mkdir(parents=True, exist_ok=True)
        desktop_icon = icons_dir / "frxx-view.png"
        if not desktop_icon.is_file():
            copyfile(icon_path, desktop_icon)

        apps_dir = Path.home() / ".local/share/applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = apps_dir/"frxx-view.desktop"
        desktop_file.write_text(
            f"[Desktop Entry]\n"
            f"Name=Frxx View\n"
            f"Exec=true\n"
            f"Icon={desktop_icon}\n"
            f"Type=Application\n"
            f"NoDisplay=true\n"
            f"Terminal=false\n"
        )
        app.setDesktopFileName('frxx-view')

        
    app.setApplicationName("Frxx View")
    app.setApplicationDisplayName("Frxx View")
    app.setWindowIcon(QIcon(icon_path))

    state = AppState(
        starting_directory,
        initial_index=args.filenum,
        parent=app,
    )
    sys.exit(app.exec())
