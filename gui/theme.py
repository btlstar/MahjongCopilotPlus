# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Shared desktop palette and native Qt controls."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPalette
from PySide6.QtWidgets import QApplication

BG = '#101113'
PANEL = '#191b1e'
CHROME = '#161719'
TEXT = '#eef0f3'
MUTED = '#959ba5'
BORDER = '#2c2f34'
GREEN = '#73c7ae'
RED = '#e27782'

STYLES = '''
QWidget { color:#eef0f3; font-family:"Microsoft YaHei UI","Segoe UI"; font-size:13px; }
QMainWindow, QWidget#Root, QWidget#Page, QScrollArea, QScrollArea > QWidget > QWidget { background:#101113; }
QFrame#Nav, QFrame#Footer { background:#161719; border:0; }
QFrame#Nav { border-bottom:1px solid #2c2f34; }
QFrame#Footer { border-top:1px solid #2c2f34; }
QFrame#Card { background:#191b1e; border:1px solid #2c2f34; border-radius:10px; }
QFrame#ModalPanel { background:#191b1e; border:1px solid #3b4049; border-radius:12px; }
QLabel { background:transparent; border:0; }
QLabel#Muted { color:#959ba5; font-size:12px; }
QLabel#Caption { color:#c7ccd3; font-size:12px; }
QLabel#Error { color:#e27782; font-size:12px; }
QLabel#Success { color:#73c7ae; font-size:12px; }
QLabel#Heading { font-size:17px; font-weight:500; }
QPushButton { background:#222428; border:1px solid #2c2f34; border-radius:7px; padding:7px 12px; }
QPushButton:hover { background:#2a2d32; border-color:#43474f; }
QPushButton:pressed { background:#343840; }
QPushButton:focus { border-color:#a9b7d0; }
QPushButton:disabled { color:#646b75; background:#1c1e22; }
QPushButton#Primary { background:#e7e9ed; color:#17191d; border-color:#e7e9ed; font-weight:500; }
QPushButton#Primary:hover { background:#ffffff; }
QPushButton#Primary:disabled { background:#51565f; color:#a3a8af; border-color:#51565f; }
QPushButton#NavButton { background:transparent; border:1px solid transparent; color:#959ba5; padding:7px 14px; }
QPushButton#NavButton:hover { background:#222428; color:#eef0f3; }
QPushButton#NavButton:checked { background:#2a2d32; color:#eef0f3; }
QPushButton#Tab { background:transparent; border:0; border-bottom:2px solid transparent; border-radius:0; color:#959ba5; padding:8px 0; }
QPushButton#Tab:hover { color:#eef0f3; }
QPushButton#Tab:checked { color:#eef0f3; border-bottom-color:#d3d8df; }
QPushButton#Quiet { background:transparent; border-color:transparent; color:#959ba5; padding:4px 6px; }
QPushButton#Quiet:checked { background:#20322d; color:#91d4be; border-color:#304a40; }
QPushButton#Quiet:hover { color:#eef0f3; background:#222428; }
QPushButton#Toggle { background:#222428; color:#c7ccd3; border:1px solid #3b4049; padding:7px 10px; }
QPushButton#Toggle:hover { background:#2a2d32; border-color:#555d69; }
QPushButton#Toggle:checked { background:#20322d; color:#91d4be; border-color:#3e6556; }
QPushButton#Toggle:checked:hover { background:#294137; border-color:#5c8a74; }
QPushButton#Preset { text-align:left; padding:13px; background:#191b1e; }
QPushButton#Preset:checked { background:#24282e; border-color:#7b8796; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background:#222428; border:1px solid #34383f; border-radius:7px; padding:7px 10px; selection-background-color:#465267; }
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color:#454a53; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color:#a9b7d0; }
QLineEdit:disabled { color:#707782; }
QComboBox { padding-right:28px; }
QComboBox::drop-down { border:0; width:25px; }
QComboBox::down-arrow { image:url(resources/ui-chevron-down.svg); width:12px; height:12px; }
QComboBox QAbstractItemView { background:#23252a; color:#eef0f3; border:1px solid #3a3e46; border-radius:6px; padding:5px; selection-background-color:#34373e; outline:0; }
QComboBox QAbstractItemView::item { min-height:29px; border:0; padding:3px 7px; }
QCheckBox { spacing:8px; background:transparent; }
QCheckBox::indicator { width:15px; height:15px; border-radius:4px; border:1px solid #555d69; background:#222428; }
QCheckBox::indicator:checked { background:#d9dfe7; border-color:#d9dfe7; image:url(resources/ui-check.svg); }
QScrollArea { border:0; }
QScrollBar:vertical { background:transparent; width:7px; margin:1px; }
QScrollBar::handle:vertical { background:#3b414a; border-radius:3px; min-height:25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
QPlainTextEdit { background:#161719; border:1px solid #2c2f34; border-radius:7px; padding:10px; color:#bcc4cf; }
QToolTip { background:#272b32; color:#eef0f3; border:1px solid #444b56; padding:5px; }
'''


def app_icon():
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor('#b8c4d3'), 3))
    p.setBrush(QColor(CHROME))
    p.drawRoundedRect(10, 8, 40, 48, 9, 9)
    p.drawLine(22, 23, 39, 23)
    p.drawLine(22, 32, 39, 32)
    p.setPen(QPen(QColor(GREEN), 3))
    p.drawLine(22, 41, 32, 41)
    p.end()
    return QIcon(pix)


def create_application():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName('MahjongCopilotPlus')
    app.setStyle('Fusion')
    palette = QPalette()
    for role,color in ((QPalette.Window,BG),(QPalette.WindowText,TEXT),
            (QPalette.Base,'#222428'),(QPalette.AlternateBase,PANEL),(QPalette.Text,TEXT),
            (QPalette.Button,'#222428'),(QPalette.ButtonText,TEXT),(QPalette.Highlight,'#34373e'),
            (QPalette.HighlightedText,TEXT),(QPalette.PlaceholderText,'#737b87'),
            (QPalette.ToolTipBase,'#272b32'),(QPalette.ToolTipText,TEXT),
            (QPalette.Light,'#404650'),(QPalette.Mid,BORDER),(QPalette.Dark,BG)):
        palette.setColor(role,QColor(color))
    palette.setColor(QPalette.Disabled,QPalette.Text,QColor('#737b87'))
    palette.setColor(QPalette.Disabled,QPalette.ButtonText,QColor('#737b87'))
    app.setPalette(palette)
    app.setFont(QFont('Microsoft YaHei UI', 9))
    from common.utils import sub_folder, Folder
    resources = sub_folder(Folder.RES).as_posix()
    app.setStyleSheet(STYLES.replace('url(resources/',f'url("{resources}/').replace('.svg);','.svg");'))
    app.setWindowIcon(app_icon())
    return app


def dark_titlebar(window):
    """Let Windows retain native resize, snap and close behavior."""
    import os
    if os.name == 'nt':
        import ctypes
        value = ctypes.c_int(1)
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(int(window.winId())), 20, ctypes.byref(value), 4)
        except OSError:
            pass
