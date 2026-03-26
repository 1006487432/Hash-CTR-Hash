from __future__ import annotations

from PySide6.QtGui import QColor

BACKGROUND = "#f4f7f2"
BACKGROUND_ALT = "#edf3ea"
SURFACE = "#ffffff"
SURFACE_ALT = "#f7faf8"
CARD = "#ffffff"
CARD_SOFT = "#f3f8f5"
TEXT = "#18242d"
MUTED = "#5f7382"
ACCENT = "#1e8fa3"
ACCENT_ALT = "#c6a24d"
SUCCESS = "#2da56c"
WARNING = "#d28c1f"
ERROR = "#cb4d4d"
BORDER = "rgba(24, 36, 45, 0.10)"
BORDER_STRONG = "rgba(30, 143, 163, 0.22)"
ROW_ALT = "rgba(30, 143, 163, 0.04)"
HOVER = "rgba(30, 143, 163, 0.08)"


def app_stylesheet() -> str:
    return f"""
    QWidget {{
        color: {TEXT};
        background: transparent;
        font-family: 'Segoe UI', 'Microsoft YaHei UI';
        font-size: 10.5pt;
    }}
    QMainWindow, QWidget#appRoot {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {BACKGROUND}, stop:0.58 {BACKGROUND_ALT}, stop:1 #e8efe8);
    }}
    QFrame#sidebar {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fbfcfa, stop:1 #eef4ef);
        border: 1px solid rgba(30, 143, 163, 0.14);
        border-radius: 24px;
    }}
    QFrame#contentPanel {{
        background: rgba(255, 255, 255, 0.58);
        border: 1px solid rgba(24, 36, 45, 0.06);
        border-radius: 24px;
    }}
    QFrame#contentShell, QFrame.card {{
        background: rgba(255, 255, 255, 0.93);
        border: 1px solid {BORDER};
        border-radius: 22px;
    }}
    QFrame.cardAlt {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {SURFACE_ALT}, stop:1 #f0f6f3);
        border: 1px solid rgba(30, 143, 163, 0.12);
        border-radius: 18px;
    }}
    QLabel#title {{
        font-size: 20pt;
        font-weight: 700;
        color: #13212a;
    }}
    QLabel#subtitle {{
        color: {MUTED};
        font-size: 10pt;
    }}
    QPushButton {{
        background: #f7fbfa;
        border: 1px solid rgba(24, 36, 45, 0.12);
        border-radius: 12px;
        padding: 10px 16px;
        font-weight: 600;
        color: {TEXT};
    }}
    QPushButton:hover {{
        border: 1px solid rgba(30, 143, 163, 0.30);
        background: #eef7f8;
    }}
    QPushButton:pressed {{
        background: #e4f0f2;
    }}
    QPushButton[class="primary"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT_ALT});
        color: #ffffff;
        border: 0px;
    }}
    QTreeWidget, QListWidget, QTableWidget, QPlainTextEdit, QLineEdit, QAbstractScrollArea {{
        background: rgba(255, 255, 255, 0.92);
        border: 1px solid rgba(24, 36, 45, 0.10);
        border-radius: 16px;
        padding: 6px;
        selection-background-color: rgba(30, 143, 163, 0.12);
        alternate-background-color: {ROW_ALT};
    }}
    QTreeWidget::item {{
        padding: 7px 6px;
        border-radius: 10px;
        margin: 2px 0px;
    }}
    QTreeWidget::item:hover {{
        background: {HOVER};
    }}
    QTreeWidget::item:selected {{
        background: rgba(30, 143, 163, 0.14);
        color: #102029;
    }}
    QTreeView::indicator {{
        width: 18px;
        height: 18px;
        margin-right: 8px;
        border-radius: 5px;
        border: 1px solid rgba(24, 36, 45, 0.22);
        background: #ffffff;
    }}
    QTreeView::indicator:unchecked:hover {{
        border: 1px solid rgba(30, 143, 163, 0.55);
        background: #f1fbfd;
    }}
    QTreeView::indicator:checked {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT_ALT});
        border: 0px;
    }}
    QTreeView::indicator:indeterminate {{
        background: {ACCENT_ALT};
        border: 0px;
    }}
    QHeaderView::section {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #eef5f4, stop:1 #f8fbfa);
        color: #18303a;
        border: 0px;
        border-bottom: 1px solid rgba(24, 36, 45, 0.10);
        padding: 10px;
        font-weight: 700;
    }}
    QTableWidget {{
        gridline-color: rgba(24, 36, 45, 0.06);
    }}
    QTableCornerButton::section {{
        background: #eef5f4;
        border: 0px;
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{
        background: transparent;
        border: 0px;
    }}
    QTabWidget::pane {{
        border: 1px solid rgba(24, 36, 45, 0.08);
        background: rgba(255, 255, 255, 0.72);
        border-radius: 18px;
        top: -1px;
        padding-top: 8px;
    }}
    QTabBar::tab {{
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid rgba(24, 36, 45, 0.10);
        color: {TEXT};
        padding: 10px 14px;
        margin-right: 6px;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
    }}
    QTabBar::tab:selected {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(30,143,163,0.16), stop:1 rgba(198,162,77,0.18));
        border: 1px solid {BORDER_STRONG};
        color: #102029;
    }}
    QTabBar::tab:hover {{
        background: #f3f8f7;
    }}
    QTabBar::close-button {{
        image: none;
        background: rgba(24, 36, 45, 0.10);
        border-radius: 7px;
        width: 14px;
        height: 14px;
    }}
    QLineEdit {{
        padding: 8px 10px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(30, 143, 163, 0.24);
        border-radius: 5px;
        min-height: 30px;
    }}
    QCheckBox {{
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid rgba(24, 36, 45, 0.18);
        background: rgba(255,255,255,0.92);
    }}
    QCheckBox::indicator:checked {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT_ALT});
        border: 0px;
    }}
    QSplitter::handle {{
        background: transparent;
    }}
    QSplitter::handle:horizontal {{
        width: 10px;
    }}
    QSplitter::handle:horizontal:hover {{
        background: rgba(30, 143, 163, 0.10);
        border-radius: 5px;
    }}
        QProgressBar {{
        background: rgba(30, 143, 163, 0.08);
        border: 1px solid rgba(24, 36, 45, 0.08);
        border-radius: 10px;
        text-align: center;
        min-height: 18px;
        color: #18303a;
    }}
    QProgressBar::chunk {{
        border-radius: 9px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e8fa3, stop:1 #c6a24d);
    }}
    """


def status_color(name: str) -> QColor:
    colors = {
        "passed": QColor(SUCCESS),
        "warning": QColor(WARNING),
        "failed": QColor(ERROR),
        "info": QColor(ACCENT),
    }
    return colors.get(name, QColor(MUTED))
