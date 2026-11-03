# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""In-window modal panels."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget, QFrame, QScrollArea
from .components import label, button, column, horizontal


class ModalOverlay(QWidget):
    closed = Signal()

    def __init__(self,parent,title):
        super().__init__(parent)
        self.setObjectName('Veil')
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet('QWidget#Veil { background:rgba(8,9,11,195); }')
        self.setGeometry(parent.rect())
        self.setFocusPolicy(Qt.StrongFocus)
        outer = column(self,16)
        panel = QFrame()
        panel.setObjectName('ModalPanel')
        panel.setMaximumWidth(470)
        panel.setMinimumWidth(min(420,max(200,parent.width()-32)))
        body = column(panel,18,12)
        header = horizontal()
        header.addWidget(label(title,'Heading'))
        header.addStretch()
        close = button('×',self.dismiss,'Quiet')
        close.setAccessibleName('关闭'+title)
        header.addWidget(close)
        body.addLayout(header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background:#191b1e; }')
        content = QWidget()
        self.body = column(content,0,10)
        self.scroll.setWidget(content)
        body.addWidget(self.scroll)
        self.panel = panel
        outer.addWidget(panel,0,Qt.AlignCenter)
        shortcut = QShortcut(QKeySequence(Qt.Key_Escape),self)
        shortcut.activated.connect(self.dismiss)
        self._escape = shortcut

    def reveal(self):
        self.scroll.setMinimumHeight(min(max(100,self.scroll.widget().sizeHint().height()+8),max(100,self.parentWidget().height()-128)))
        self.panel.setMaximumHeight(self.parentWidget().height()-32)
        self.show()
        self.raise_()
        self.setFocus()

    def dismiss(self):
        self.hide()
        self.closed.emit()
        self.deleteLater()

