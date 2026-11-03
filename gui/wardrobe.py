# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Honest wardrobe controls: expansion switch and read-only outfit references."""
import os
from ruamel.yaml import YAML
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget, QScrollArea, QPushButton
from mjmax.paths import CONFIG
from .components import Card, Switch, label, button, column, horizontal, setting_row

OUTFITS = {
    '竹影墨韵': [('桌布','清辉竹影'),('牌背','翠竹墨影'),('立直棒','青竹伞'),
        ('和牌特效','墨韵'),('立直特效','挥毫'),('鸣牌指示','森之眷顾'),
        ('手的样式','默认，随雀士／服饰'),('头像框','竹福滚滚'),('牌面','默认'),('大厅背景','听竹别苑')],
    '星月水光': [('桌布','星月夜'),('牌背','星幕绘卷'),('立直棒','绚烂烟花'),
        ('和牌特效','涟漪之空'),('立直特效','水漾星光'),('鸣牌指示','众星捧月'),
        ('手的样式','蓝猫爪'),('头像框','北风之诗'),('牌面','默认'),('大厅背景','萤火谧语')],
}


class OutfitButton(QPushButton):
    def __init__(self,name,description,colors):
        super().__init__(name+'\n'+description)
        self.colors = colors.split(',')
        self.setObjectName('Preset')
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(112)
        self.setStyleSheet('padding-top:43px;')

    def paintEvent(self,event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(13,13,self.width()-26,22),4,4)
        p.setClipPath(path)
        width = (self.width()-26)/4
        for i,color in enumerate(self.colors):
            p.fillRect(QRectF(13+i*width,13,width,22),QColor(color))


def expansion_enabled():
    path = CONFIG / 'settings.yaml'
    if not path.exists():
        path = CONFIG / 'settings.example.yaml'
    settings = YAML(typ='safe').load(path.read_text(encoding='utf-8')) if path.exists() else {}
    return bool((settings or {}).get('plugin_enable',{}).get('mod',False))


def save_expansion(enabled):
    """Change only the enable flag; never touch the user's equipped item pages."""
    path = CONFIG / 'settings.yaml'
    yaml = YAML()
    settings = yaml.load(path.read_text(encoding='utf-8')) if path.exists() else {}
    settings = settings or {}
    settings.setdefault('plugin_enable',{})['mod'] = bool(enabled)
    pending = path.with_suffix('.yaml.pending')
    try:
        with pending.open('w',encoding='utf-8') as stream:
            yaml.dump(settings,stream)
        os.replace(pending,path)
    finally:
        if pending.exists():
            pending.unlink()


class WardrobePage(QScrollArea):
    def __init__(self,owner):
        super().__init__()
        self.owner = owner
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget()
        page.setObjectName('Page')
        body = column(page,18,12)
        engine = Card()
        try:
            enabled = expansion_enabled()
            error = None
        except Exception as exc:
            enabled,error = False,exc
        self.toggle = Switch(enabled,self._toggle,'启用 MajsoulMax')
        engine.body.addWidget(setting_row('装扮扩展 · MajsoulMax','雀魂的角色、服饰与装扮',self.toggle))
        self.result = label('读取装扮扩展配置失败。' if error else '', 'Error' if error else 'Muted',True)
        engine.body.addWidget(self.result)
        body.addWidget(engine)
        body.addWidget(label('搭配参考 · 2 套方案'))
        choices = horizontal(spacing=10)
        self.presets = []
        for index,(name,description,colors) in enumerate((
                ('竹影墨韵','青竹 · 水墨','#344d43,#729784,#d2d8cc,#303b34'),
                ('星月水光','星月 · 水光','#26344c,#567a9c,#afbfd2,#c8b58d'))):
            preset = OutfitButton(name,description,colors)
            preset.clicked.connect(lambda checked=False,n=name:self.select(n))
            choices.addWidget(preset,1)
            self.presets.append(preset)
        body.addLayout(choices)
        self.details = Card('竹影墨韵','在游戏内装备')
        self.rows = []
        self.row_widgets = []
        for index in range(10):
            row = QWidget()
            layout = horizontal(row)
            slot,value = label(''),label('','')
            slot.setMinimumWidth(90)
            layout.addWidget(slot)
            layout.addWidget(value,1)
            self.details.body.addWidget(row)
            row.setVisible(index<3)
            self.rows.append((slot,value))
            self.row_widgets.append(row)
        more = button('其余 7 项 ⌄',name='Quiet',checkable=True)
        more.toggled.connect(lambda expanded:[row.setVisible(expanded) for row in self.row_widgets[3:]])
        self.details.body.addWidget(more,0,Qt.AlignLeft)
        body.addWidget(self.details)
        body.addStretch()
        self.setWidget(page)
        self.select('竹影墨韵')

    def select(self,name):
        self.details.header.itemAt(0).widget().setText(name)
        for item in self.presets:
            item.setChecked(item.text().split('\n')[0]==name)
        for (slot,value),(slot_name,item_name) in zip(self.rows,OUTFITS[name]):
            slot.setText(slot_name)
            value.setText(item_name)

    def _toggle(self,enabled):
        try:
            save_expansion(enabled)
            self.owner.bot_manager.mitm_proxinject_need_update = True
            self.result.setText('已保存；关闭游戏浏览器后更新连接。' if self.owner.bot_manager.browser.is_running() else '已保存，正在更新连接。')
        except Exception:
            self.toggle.blockSignals(True)
            self.toggle.setChecked(not enabled)
            self.toggle.blockSignals(False)
            self.result.setText('保存失败，原配置已保留。')
