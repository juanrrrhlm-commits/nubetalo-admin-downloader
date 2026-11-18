from pathlib import Path
import math
import sys
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


def assets_dir():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets'


def neon_glow(widget, radius=20, alpha=100):
    glow = QGraphicsDropShadowEffect(widget)
    glow.setBlurRadius(radius)
    glow.setOffset(0, 0)
    color = QColor('#57ff93')
    color.setAlpha(alpha)
    glow.setColor(color)
    widget.setGraphicsEffect(glow)
    return glow


def apply_theme(app):
    for path in assets_dir().glob('*.ttf'):
        QFontDatabase.addApplicationFont(str(path))
    app.setFont(QFont('IBM Plex Sans', 10))
    app.setWindowIcon(QIcon(str(assets_dir() / 'logo.png')))
    app.setStyle('Fusion')
    app.setStyleSheet('''
        QWidget { background: #080c0a; color: #edf7f0; font-family: "IBM Plex Sans"; font-size: 13px; }
        QMainWindow { background: #080c0a; }
        QLabel#subtitle, QLabel#muted { color: #a8bbb0; }
        QLabel { background: transparent; }
        QLabel#heading { font-size: 20px; font-weight: 600; }
        QLabel#emptyTitle { font-size: 24px; font-weight: 600; }
        QLabel#brand { font-size: 16px; font-weight: 600; }
        QFrame#sidebar { background: #0f1712; border-right: 1px solid #20372a; }
        QFrame#toolbar { border-bottom: 1px solid #20372a; }
        QPushButton { background: #15251b; border: 1px solid #2d4c39; border-radius: 7px; padding: 8px 13px; }
        QPushButton:hover { background: #1c3c2a; border-color: #57ff93; }
        QPushButton:pressed { background: #225c3c; }
        QPushButton:disabled { color: #738c7b; border-color: #20372a; }
        QPushButton:focus, QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border: 2px solid #b1ffce; }
        QPushButton#primary { background: #57f58b; border-color: #57f58b; color: #07150c; font-weight: 600; }
        QPushButton#primary:hover { background: #82ffac; }
        QPushButton#donate { color: #ff9dad; background: transparent; }
        QPushButton#policy:checked { background: #164b2d; color: #b1ffce; border-color: #57f58b; }
        QPushButton#filter { background: transparent; border: 0; text-align: left; padding: 11px 13px; }
        QPushButton#filter:checked { background: #153c27; color: #b1ffce; border: 1px solid #318554; }
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QTimeEdit, QComboBox { background: #101d15; border: 1px solid #315640; border-radius: 6px; padding: 7px; selection-background-color: #57f58b; }
        QComboBox QAbstractItemView { background: #111e16; selection-background-color: #16482d; }
        QTreeWidget { background: #080c0a; border: 0; outline: 0; alternate-background-color: #0f1712; }
        QTreeWidget::item { padding: 12px 7px; border-bottom: 1px solid #1b3023; }
        QTreeWidget::item:selected { background: #153c27; color: #edf7f0; }
        QHeaderView::section { background: #0f1712; color: #a8bbb0; border: 0; border-bottom: 1px solid #2d4c39; padding: 11px 8px; }
        QProgressBar { border: 0; background: #20372a; border-radius: 4px; text-align: center; min-height: 8px; max-height: 8px; }
        QProgressBar::chunk { background: #57f58b; border-radius: 4px; }
        QTabWidget::pane { border: 1px solid #2d4c39; border-radius: 6px; }
        QTabBar::tab { background: #0f1712; padding: 10px 12px; border-bottom: 2px solid transparent; }
        QTabBar::tab:selected { color: #b1ffce; border-bottom-color: #57f58b; }
        QCheckBox { spacing: 9px; padding: 5px 0; }
        QCheckBox::indicator { width: 17px; height: 17px; }
        QMenu { background: #111e16; border: 1px solid #315640; padding: 5px; }
        QMenu::item { padding: 8px 25px; }
        QMenu::item:selected { background: #16482d; }
        QScrollBar:vertical { background: #0f1712; width: 9px; }
        QScrollBar::handle:vertical { background: #315640; border-radius: 4px; min-height: 30px; }
        QToolTip { background: #111e16; color: #edf7f0; border: 1px solid #57f58b; padding: 6px; }
    ''')


def size_text(value):
    if value < 1000:
        return f'{value} B'
    for unit in ('KB', 'MB', 'GB', 'TB'):
        value /= 1000
        if value < 1000:
            return f'{value:.1f} {unit}'
    return f'{value:.1f} TB'


def eta_text(seconds, language='es'):
    if not math.isfinite(seconds) or seconds <= 0:
        return '—'
    seconds = max(1, int(seconds))
    units = [
        (365 * 86400, ('año', 'años'), ('year', 'years')),
        (30 * 86400, ('mes', 'meses'), ('month', 'months')),
        (7 * 86400, ('semana', 'semanas'), ('week', 'weeks')),
        (86400, ('día', 'días'), ('day', 'days')),
        (3600, ('hora', 'horas'), ('hour', 'hours')),
    ]
    for duration, spanish, english in units:
        if seconds >= duration:
            amount = seconds // duration
            names = english if language == 'en' else spanish
            return f'{amount} {names[amount != 1]}'
    return f'{seconds // 60}:{seconds % 60:02}'
