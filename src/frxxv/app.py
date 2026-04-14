"""
Application entry point.

    from frxxv.app import main
    main()              # empty panels
    main(demo=True)     # test figures
"""
import sys
from PySide6.QtWidgets import QApplication

from frxxv.main_window import MainWindow


def main(demo: bool = False):
    app = QApplication(sys.argv)
    window = MainWindow()

    if demo:
        from frxxv.plotting.ppi import demo_plot_factory
        from frxxv.config import LAYOUTS

        window.panel_grid.set_plot_factory(demo_plot_factory)
        visible = len(LAYOUTS[window.state.layout])
        for i in range(visible):
            window.panel_grid.replot_panel(i)

    window.show()
    sys.exit(app.exec())