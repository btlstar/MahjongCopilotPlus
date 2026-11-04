# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Small, reusable Qt components for the dark desktop."""
from PySide6.QtCore import Qt, QRectF, QSize
from pathlib import Path
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QIcon
from PySide6.QtWidgets import (QAbstractButton, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget, QSizePolicy, QStyledItemDelegate, QStyle, QLineEdit)
from common.presentation import tile_data
from .theme import MUTED, TEXT


class SecretEdit(QLineEdit):
    """Password entry with an accessible, reversible trailing eye action."""
    def __init__(self,value='',parent=None):
        super().__init__(value,parent)
        self.setEchoMode(QLineEdit.Password)
        self.visibility_action = self.addAction(QIcon(),QLineEdit.TrailingPosition)
        self.visibility_action.setCheckable(True)
        self.visibility_action.toggled.connect(self._reveal)
        self._reveal(False)

    def _reveal(self,visible):
        self.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        action = self.visibility_action
        text = '隐藏密钥' if visible else '显示密钥'
        action.setText(text)
        action.setToolTip(text)
        icon = 'ui-eye-off.svg' if visible else 'ui-eye.svg'
        action.setIcon(QIcon(str(Path(__file__).resolve().parent.parent/'resources'/icon)))

    def conceal(self):
        self.visibility_action.setChecked(False)


class TextLabel(QLabel):
    def setText(self,text):
        super().setText(text)
        self.setVisible(bool(text))

    def clear(self):
        self.setText('')


def label(text='', name='Muted', wrap=False):
    item = TextLabel(text)
    item.setObjectName(name)
    item.setWordWrap(wrap)
    if not text:
        item.hide()
    return item


def button(text, callback=None, name='', checkable=False):
    item = QPushButton(text)
    item.setObjectName(name)
    item.setCheckable(checkable)
    item.setCursor(Qt.PointingHandCursor)
    if callback:
        item.clicked.connect(callback)
    return item


def column(parent=None, margin=0, spacing=12):
    layout = QVBoxLayout(parent)
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(spacing)
    return layout


def horizontal(parent=None, margin=0, spacing=8):
    layout = QHBoxLayout(parent)
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(spacing)
    return layout


class Card(QFrame):
    def __init__(self, title=None, detail='', parent=None):
        super().__init__(parent)
        self.setObjectName('Card')
        self.body = column(self, 16, 10)
        self.header = None
        if title:
            self.header = horizontal(spacing=10)
            self.header.addWidget(label(title, 'Caption'))
            self.header.addStretch()
            self.detail = label(detail)
            self.header.addWidget(self.detail)
            self.body.addLayout(self.header)


class Switch(QAbstractButton):
    def __init__(self, checked=False, callback=None, text='', parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setAccessibleName(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(34, 24)
        if callback:
            self.toggled.connect(callback)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#d9dfe7' if self.isChecked() else '#414650'))
        p.drawRoundedRect(QRectF(1, 3, 32, 18), 9, 9)
        p.setBrush(QColor('#30343b' if self.isChecked() else '#adb4be'))
        p.drawEllipse(QRectF(18 if self.isChecked() else 4, 6, 12, 12))
        if self.hasFocus():
            p.setPen(QPen(QColor('#a9b7d0'), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(.5,.5,33,23), 9,9)


class QuietDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option.state &= ~QStyle.State_HasFocus
        super().paint(painter, option, index)


def setting_row(title, detail, control):
    row = QWidget()
    layout = horizontal(row, spacing=18)
    copy = column(spacing=3)
    copy.addWidget(label(title, ''))
    if detail:
        copy.addWidget(label(detail, wrap=True))
    layout.addLayout(copy, 1)
    layout.addWidget(control, 0, Qt.AlignVCenter)
    row.setMinimumHeight(48)
    return row


class TokenView(QWidget):
    """Paint real tiles, including red fives, without Mahjong emoji fonts."""
    def __init__(self, tokens=None, primary=False, hand=False, parent=None):
        super().__init__(parent)
        self.tokens = tokens or []
        self.primary, self.hand = primary, hand
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setAccessibleName('麻将牌')

    def set_tokens(self, tokens):
        if self.tokens != tokens:
            self.tokens = tokens
            self.updateGeometry()
            self.update()

    def hasHeightForWidth(self):
        return True

    def font_for_text(self):
        font = QFont('Microsoft YaHei UI')
        font.setPixelSize(20 if self.primary else 14)
        return font

    def _layout(self, width):
        tw, th = (32,43) if self.primary else (27,36) if self.hand else (23,30)
        fm = QFontMetricsF(self.font_for_text())
        x, y, boxes = 0., 0., []
        for token in self.tokens:
            parts = [token] if 'tile' in token or 'gap' in token else [{'text': c} for c in token.get('text','')]
            for part in parts:
                size = tw+4 if 'tile' in part else part['gap'] if 'gap' in part else fm.horizontalAdvance(part['text'])
                if x and x+size > max(1, width):
                    y += th+6
                    x = 0.
                boxes.append((part, QRectF(x,y,size,th)))
                x += size
        return boxes, int(y+th) if boxes else 0

    def heightForWidth(self, width):
        return self._layout(width)[1]

    def sizeHint(self):
        return QSize(180, self.heightForWidth(max(180, self.width())))

    def minimumSizeHint(self):
        return QSize(45, 43 if self.primary else 36 if self.hand else 30)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        boxes, _ = self._layout(self.width())
        for token, rect in boxes:
            if 'tile' in token:
                self.paint_tile(p, rect.adjusted(0,0,-4,0), token['tile'])
            elif 'text' in token:
                p.setPen(QColor(TEXT if self.primary else '#c7ccd3'))
                p.setFont(self.font_for_text())
                p.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, token['text'])

    @staticmethod
    def paint_tile(p, rect, tile):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#b4b0a5'))
        p.drawRoundedRect(rect,4,4)
        p.setBrush(QColor('#e1dfd8'))
        p.drawRoundedRect(rect.adjusted(0,0,0,-2),4,4)
        p.setPen(QColor(tile['color']))
        font = QFont('Microsoft YaHei UI')
        font.setPixelSize(round(rect.height()*.49))
        p.setFont(font)
        if tile['suit']:
            p.drawText(rect.adjusted(0,1,0,-rect.height()*.31), Qt.AlignCenter, tile['value'])
            font.setPixelSize(round(rect.height()*.27))
            p.setFont(font)
            p.drawText(rect.adjusted(0,rect.height()*.52,0,-3), Qt.AlignCenter, tile['suit'])
        else:
            p.drawText(rect.adjusted(0,0,0,-2), Qt.AlignCenter, tile['value'])
        if tile.get('red'):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#c84d52'))
            p.drawEllipse(QRectF(rect.right()-5, rect.top()+3, 3, 3))


class AdviceView(QWidget):
    def __init__(self, compact=False, parent=None):
        super().__init__(parent)
        self.compact = compact
        self.body = column(self, 0, 6 if compact else 8)
        self.empty = label('等待 AI 建议…' if compact else '打开游戏并进入对局后，建议会显示在这里。', wrap=True)
        self.body.addWidget(self.empty)
        self._signature = None
        self.rows = []

    def set_advice(self, rows):
        if rows == self._signature:
            return
        self._signature = rows
        for widget in self.rows:
            self.body.removeWidget(widget)
            widget.deleteLater()
        self.rows = []
        self.empty.setVisible(not rows)
        for i, data in enumerate(rows):
            if i == 1:
                separator = QFrame()
                separator.setFixedHeight(1)
                separator.setStyleSheet('background:#2c2f34;')
                self.body.addWidget(separator)
                self.rows.append(separator)
            row = QWidget()
            layout = horizontal(row, spacing=8)
            view = TokenView(data['tokens'], primary=(i==0 and not self.compact))
            layout.addWidget(view, 1)
            probability = label('' if data['weight'] is None else f"{round(data['weight']*100)}%", '')
            probability.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            probability.setStyleSheet(f'font-size:{16 if self.compact and i==0 else 22 if i==0 else 13}px;color:{TEXT if i==0 else MUTED};')
            probability.setMinimumWidth(36 if self.compact else 46)
            layout.addWidget(probability)
            self.body.addWidget(row)
            self.rows.append(row)
        self.updateGeometry()


class HandView(TokenView):
    def __init__(self):
        super().__init__(hand=True)

    def set_hand(self, hand, drawn=None):
        tokens = [{'tile': tile_data(code)} for code in hand]
        if drawn:
            tokens += [{'gap':9}, {'tile':tile_data(drawn)}]
        self.set_tokens(tokens)
