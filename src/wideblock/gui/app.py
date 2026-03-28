from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .theme import BACKGROUND, BACKGROUND_ALT, SURFACE, SURFACE_ALT, TEXT, MUTED, ACCENT, app_stylesheet


def create_application() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Wide-Block Algorithm Lab")
    app.setFont(QFont("Segoe UI", 10))

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BACKGROUND))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(BACKGROUND_ALT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    app.setPalette(palette)
    app.setStyleSheet(app_stylesheet())
    return app


def launch() -> int:
    app = create_application()
    window = MainWindow()
    window.show()
    return app.exec()
