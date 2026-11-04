# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Embedded settings pages; drafts stay separate from running AI state."""
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QStackedWidget, QScrollArea, QLineEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QFileDialog, QSizePolicy)
from common.utils import GAME_MODES, sub_file, Folder
from .boss_key import parse_hotkey
from .components import Card, Switch, QuietDelegate, label, button, column, horizontal, setting_row

PROVIDERS = [('AkagiOT','AkagiOT'), ('MJAI','MJAPI'), ('本地模型','Local')]
AI_KEYS = ('model_type','model_file','model_file_3p','akagi_ot_url','akagi_ot_apikey',
           'akagi_ot_protocol','akagi_v3_url','akagi_v3_apikey','akagi_v3_model_4p','akagi_v3_model_3p',
           'mjapi_url','mjapi_user','mjapi_secret','mjapi_model_select')


def valid_url(value, optional=False):
    parsed = urlparse(value)
    if optional and not value:
        return True
    return parsed.scheme in ('http','https') and bool(parsed.hostname)


def test_ai_connection(values,fetch_only=False):
    """Explicit user-triggered test; never starts a match or registers an account."""
    provider = values['model_type']
    if provider == 'Local':
        from bot.local.bot_local import BotMortalLocal
        from common.utils import GameMode
        paths = {mode:sub_file(Folder.MODEL, values[key]) for mode,key in
                 ((GameMode.MJ4P,'model_file'), (GameMode.MJ3P,'model_file_3p')) if values[key]}
        bot = BotMortalLocal(paths)
        missing = [mode.value for mode in paths if mode not in bot.supported_modes]
        if missing:
            raise ValueError('这些模式的模型未能加载：'+' / '.join(missing))
        return {'message':'模型验证通过：'+' / '.join(mode.value for mode in bot.supported_modes)}
    if provider == 'AkagiOT':
        if values['akagi_ot_protocol']=='v3':
            from bot.akagiot.v3 import AkagiV3Client,validate_models
            models = AkagiV3Client(values['akagi_v3_url'],values['akagi_v3_apikey']).catalog()
            if not models:
                raise ValueError('密钥已授权，但没有可用模型。')
            error = None
            try:
                validate_models(models,values['akagi_v3_model_4p'],values['akagi_v3_model_3p'])
            except ValueError as exc:
                if not fetch_only:
                    raise
                error = str(exc)
            return {'message':error or f'已获取 {len(models)} 个可用模型。密钥与模型检查通过；尚未执行推理。',
                    'ot_models':models,'selection_error':bool(error)}
        import requests
        response = requests.post(values['akagi_ot_url'].rstrip('/')+'/check',
                                 headers={'Authorization':values['akagi_ot_apikey']}, timeout=8)
        response.raise_for_status()
        if response.json().get('result') != 'success':
            raise ValueError('服务未通过授权检查，请检查 API Key。')
        return {'message':'旧版 OT 授权通过；此接口未指定模型，使用服务端默认。要选择模型请切换 Akagi v3。'}
    from bot.mjapi.mjapi import MjapiClient
    client = MjapiClient(values['mjapi_url'].rstrip('/'), timeout=8)
    if not values['mjapi_user'] or not values['mjapi_secret']:
        raise ValueError('请填写已有账户的用户名和密钥。连接测试不会创建账户。')
    client.login(values['mjapi_user'], values['mjapi_secret'])
    models = client.list_models()
    if not models:
        raise ValueError('服务未返回可用模型。')
    return {'message':f'MJAI 连接成功 · {len(models)} 个可用模型', 'models':models}


class SettingsPage(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.setObjectName('Page')
        self.owner, self.st = owner, owner.st
        self.fields = {}
        self.layout_main = column(self, 18, 14)
        tabs = horizontal(spacing=22)
        self.tab_buttons = []
        self.pages = QStackedWidget()
        for i, text in enumerate(('显示','AI 连接','平台','高级')):
            item = button(text, lambda checked=False,index=i:self.select_tab(index), 'Tab', True)
            tabs.addWidget(item)
            self.tab_buttons.append(item)
        tabs.addStretch()
        self.layout_main.addLayout(tabs)
        self.layout_main.addWidget(self.pages,1)
        for builder in (self._display, self._ai, self._platforms, self._advanced):
            page = QWidget()
            page.setObjectName('Page')
            body = column(page, 0, 12)
            builder(body)
            body.addStretch()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidget(page)
            self.pages.addWidget(scroll)
        self.select_tab(0)

    def select_tab(self, index):
        self.pages.setCurrentIndex(index)
        for i, item in enumerate(self.tab_buttons):
            item.setChecked(i == index)

    def _combo(self, key, items, current=None):
        control = QComboBox()
        control.setItemDelegate(QuietDelegate(control))
        control.setObjectName(key)
        for item in items:
            if isinstance(item,tuple):
                control.addItem(*item)
            else:
                control.addItem(str(item),item)
        if current is not None:
            index = control.findData(current)
            if index < 0:
                control.addItem(str(current),current)
                index = control.count()-1
            control.setCurrentIndex(index)
        self.fields[key] = control
        return control

    def _entry(self, key, value=None, password=False):
        entry = QLineEdit(str(getattr(self.st,key,'') if value is None else value))
        entry.setObjectName(key)
        entry.setAccessibleName(key)
        if password:
            entry.setEchoMode(QLineEdit.Password)
        self.fields[key] = entry
        return entry

    def _field(self, body, title, widget):
        body.addWidget(label(title))
        body.addWidget(widget)

    def _switch(self, body, key, title, detail=''):
        control = Switch(bool(getattr(self.st,key)), text=title)
        control.setObjectName(key)
        self.fields[key] = control
        body.addWidget(setting_row(title,detail,control))
        return control

    def _result(self, body):
        item = label('', wrap=True)
        body.addWidget(item)
        return item

    @staticmethod
    def feedback(target, text, error=False):
        target.setText(text)
        target.setStyleSheet('color:#e27782;' if error else 'color:#73c7ae;')

    def _display(self, body):
        card = Card()
        card.body.addWidget(setting_row('深色主题','应用到主界面、菜单和提示窗。',label('默认')))
        guide = self._switch(card.body,'enable_overlay','游戏内 AI 提示','即时生效，与顶栏开关同步；关闭后仍可在主界面查看建议。')
        guide.toggled.connect(self._set_game_overlay)
        self._switch(card.body,'show_game_status_overlay','游戏内状态角标','默认隐藏，避免遮挡画面。')
        body.addWidget(card)
        card = Card()
        self._switch(card.body,'boss_key_enabled','老板键','隐藏或恢复主界面和游戏浏览器。')
        presets = [('Alt+Q（推荐）','Alt+Q'),('Alt+Z','Alt+Z'),('Alt+X','Alt+X'),('自定义','custom')]
        preset = self._combo('boss_preset',presets,self.st.boss_key if self.st.boss_key in ('Alt+Q','Alt+Z','Alt+X') else 'custom')
        card.body.addWidget(setting_row('快捷键预设','两个按键，左手即可操作。',preset))
        custom = self._entry('boss_key')
        self.custom_hotkey_row = setting_row('自定义快捷键','Ctrl 或 Alt + 字母、数字、F1–F11。',custom)
        self.custom_hotkey_row.setVisible(preset.currentData()=='custom')
        preset.currentIndexChanged.connect(lambda:self.custom_hotkey_row.setVisible(preset.currentData()=='custom'))
        card.body.addWidget(self.custom_hotkey_row)
        body.addWidget(card)
        self.display_result = self._result(body)
        actions = horizontal()
        actions.addStretch()
        actions.addWidget(button('保存显示设置',self.save_display,'Primary'))
        body.addLayout(actions)

    def save_display(self):
        try:
            preset = self.fields['boss_preset'].currentData()
            key = parse_hotkey(self.fields['boss_key'].text() if preset=='custom' else preset)[0]
            enabled = self.fields['boss_key_enabled'].isChecked()
            ok,error = self.owner.configure_boss_key(enabled,key)
            if not ok:
                raise ValueError(error)
            changes = {'boss_key_enabled':enabled,'boss_key':key,
                       'show_game_status_overlay':self.fields['show_game_status_overlay'].isChecked()}
            self.owner.save_settings(changes)
            self.feedback(self.display_result,'显示设置已保存。')
        except (ValueError,OSError) as error:
            self.feedback(self.display_result,str(error),True)

    def _set_game_overlay(self,enabled):
        try:
            self.owner.save_settings({'enable_overlay':enabled})
        except OSError as error:
            self.sync_game_overlay_choice()
            self.feedback(self.display_result,str(error),True)

    def sync_game_overlay_choice(self):
        control = self.fields['enable_overlay']
        previous = control.blockSignals(True)
        control.setChecked(self.st.enable_overlay)
        control.blockSignals(previous)

    def _ai(self, body):
        card = Card()
        self._field(card.body,'AI 来源',self._combo('model_type',PROVIDERS,self.st.model_type))
        self.ai_stack = QWidget()
        self.ai_stack.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Maximum)
        stack_body = column(self.ai_stack,0,0)
        self.ai_provider_pages = []
        for provider in ('AkagiOT','MJAPI','Local'):
            page = QWidget()
            layout = column(page,0,9)
            if provider=='Local':
                for key,title in (('model_file','四麻模型文件'),('model_file_3p','三麻模型文件')):
                    self._field(layout,title,self._model_file(key,title))
                layout.addWidget(label('选择兼容的 Mortal 权重；两种模式分别配置，可只启用一种。',wrap=True))
            elif provider=='AkagiOT':
                protocol = self._combo('akagi_ot_protocol',[('Akagi v3 · 可选模型','v3'),('旧版 OT · 服务端默认','legacy')],self.st.akagi_ot_protocol)
                self._field(layout,'接口',protocol)
                self.ot_forms = {}
                for kind in ('v3','legacy'):
                    form = QWidget()
                    form_body = column(form,0,9)
                    prefix = 'akagi_v3' if kind=='v3' else 'akagi_ot'
                    self._field(form_body,'服务地址',self._entry(prefix+'_url'))
                    self._field(form_body,'API Key',self._entry(prefix+'_apikey',password=True))
                    if kind=='v3':
                        from bot.akagiot.v3 import DEFAULT_4P,DEFAULT_3P
                        choices = horizontal(spacing=12)
                        for key,title,default in (('akagi_v3_model_4p','四麻模型',DEFAULT_4P),('akagi_v3_model_3p','三麻模型',DEFAULT_3P)):
                            box = QWidget()
                            fields = column(box,0,6)
                            control = self._combo(key,[('',''),(default,default)],getattr(self.st,key))
                            control.setEditable(True)
                            control.lineEdit().setPlaceholderText('留空：服务端默认')
                            control.setMinimumWidth(0)
                            control.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
                            self._field(fields,title,control)
                            choices.addWidget(box,1)
                        form_body.addLayout(choices)
                        form_body.addWidget(label('使用 Akagi v3 对应的密钥；旧版 OT 密钥不保证通用。预设模型以服务端授权列表为准。',wrap=True))
                        self.ot_model_status = label('尚无推理回报。连接测试仅验证授权与模型可用性。',wrap=True)
                        form_body.addWidget(self.ot_model_status)
                    else:
                        form_body.addWidget(label('旧接口不提供模型选择。连接成功仅代表密钥授权通过，不能确认具体模型。',wrap=True))
                    layout.addWidget(form)
                    self.ot_forms[kind] = form
                protocol.currentIndexChanged.connect(self._ot_protocol_changed)
                self._ot_protocol_changed()
            else:
                self._field(layout,'服务地址',self._entry('mjapi_url'))
                self._field(layout,'用户名',self._entry('mjapi_user'))
                self._field(layout,'账户密钥',self._entry('mjapi_secret',password=True))
                model = self._combo('mjapi_model_select',self.st.mjapi_models,self.st.mjapi_model_select)
                model.setEditable(True)
                self._field(layout,'模型',model)
                layout.addWidget(label('测试连接后获取可用模型，不会自动创建账户。',wrap=True))
            stack_body.addWidget(page)
            self.ai_provider_pages.append(page)
        card.body.addWidget(self.ai_stack)
        self.ai_result = self._result(card.body)
        actions = horizontal()
        self.test_button = button('测试连接',self.test_connection)
        actions.addWidget(self.test_button)
        self.fetch_ot_button = button('获取可用模型',lambda checked=False:self.test_connection(fetch_only=True),'Quiet')
        actions.addWidget(self.fetch_ot_button)
        actions.addStretch()
        actions.addWidget(button('保存配置',self.save_ai,'Primary'))
        card.body.addLayout(actions)
        body.addWidget(card)
        body.addWidget(label('各来源的配置分别保留。对局中保存的 AI 更改会在当前对局结束后加载。',wrap=True))
        self.fields['model_type'].currentIndexChanged.connect(self._provider_changed)
        self._provider_changed()

    def _ot_protocol_changed(self):
        protocol = self.fields['akagi_ot_protocol'].currentData()
        for kind,form in self.ot_forms.items():
            form.setVisible(kind==protocol)
        if hasattr(self,'fetch_ot_button'):
            self.fetch_ot_button.setVisible(self.fields['model_type'].currentData()=='AkagiOT' and protocol=='v3')
            self.ai_result.clear()

    def refresh_model_status(self,bot):
        if getattr(bot,'last_error',None):
            self.ot_model_status.setText('推理未完成：'+bot.last_error)
            self.ot_model_status.setStyleSheet('color:#e27782;')
        elif getattr(bot,'model_confirmed',False):
            self.ot_model_status.setText('服务端实际模型：'+bot.last_served_model)
            self.ot_model_status.setStyleSheet('color:#73c7ae;')
        else:
            self.ot_model_status.setText('尚无 v3 推理回报；连接测试不代表已经使用所选模型。')
            self.ot_model_status.setStyleSheet('color:#959ba5;')

    def _model_file(self,key,title):
        box = QWidget()
        layout = horizontal(box)
        entry = self._entry(key)
        if entry.text() in ('mortal.pth','mortal_3p.pth') and not Path(sub_file(Folder.MODEL,entry.text())).is_file():
            entry.clear()
        entry.setPlaceholderText('选择模型文件…')
        layout.addWidget(entry,1)
        def browse():
            current = Path(sub_file(Folder.MODEL,entry.text()))
            path,_ = QFileDialog.getOpenFileName(self,title,str(current.parent),'Mortal 模型 (*.pth *.pt);;所有文件 (*)')
            if path:
                entry.setText(path)
        layout.addWidget(button('浏览…',browse))
        return box

    def _provider_changed(self):
        provider = self.fields['model_type'].currentData()
        for i,page in enumerate(self.ai_provider_pages):
            page.setVisible(i==('AkagiOT','MJAPI','Local').index(provider))
        self.ai_stack.updateGeometry()
        if self.pages.count()>1:
            self.pages.widget(1).verticalScrollBar().setValue(0)
        self.test_button.setText('验证模型' if provider=='Local' else '测试连接')
        self.fetch_ot_button.setVisible(provider=='AkagiOT' and self.fields['akagi_ot_protocol'].currentData()=='v3')
        self.ai_result.clear()

    def ai_values(self):
        values = {}
        for key in AI_KEYS:
            item = self.fields[key]
            values[key] = item.currentData() if key in ('model_type','akagi_ot_protocol') else item.currentText().strip() if isinstance(item,QComboBox) else item.text().strip()
        provider = values['model_type']
        if provider=='Local':
            selected = [values[key] for key in ('model_file','model_file_3p') if values[key]]
            if not selected:
                raise ValueError('请至少选择一个模型文件。')
            for path in selected:
                if not Path(sub_file(Folder.MODEL,path)).is_file():
                    raise ValueError('模型文件不存在，请使用“浏览…”重新选择。')
        else:
            url_key = ('akagi_v3_url' if values['akagi_ot_protocol']=='v3' else 'akagi_ot_url') if provider=='AkagiOT' else 'mjapi_url'
            if not valid_url(values[url_key]):
                raise ValueError('请输入有效的 http:// 或 https:// 服务地址。')
            if provider=='MJAPI' and (not values['mjapi_user'] or not values['mjapi_secret']):
                raise ValueError('请填写已有账户的用户名和密钥。')
            if provider=='AkagiOT' and values['akagi_ot_protocol']=='v3' and not values['akagi_v3_apikey']:
                raise ValueError('请填写 Akagi v3 对应的 API Key；不会自动使用旧服务的密钥。')
        return values

    def save_ai(self):
        try:
            values = self.ai_values()
            if values['model_type']=='MJAPI':
                values['mjapi_models'] = [self.fields['mjapi_model_select'].itemText(i) for i in range(self.fields['mjapi_model_select'].count())]
            self.owner.save_settings(values)
            self.feedback(self.ai_result,'配置已保存，当前对局结束后加载。' if self.owner.bot_manager.is_in_game() else '配置已保存，正在加载 AI…')
        except (ValueError,OSError) as error:
            self.feedback(self.ai_result,str(error),True)

    def test_connection(self,fetch_only=False):
        try:
            values = self.ai_values()
        except ValueError as error:
            self.feedback(self.ai_result,str(error),True)
            return
        self.test_button.setEnabled(False)
        self.fetch_ot_button.setEnabled(False)
        self.ai_result.setText('正在验证模型…' if values['model_type']=='Local' else '正在测试连接…')
        provider = values['model_type']
        def complete(result,error):
            self.test_button.setEnabled(True)
            self.fetch_ot_button.setEnabled(True)
            if provider!=self.fields['model_type'].currentData():
                return
            try:
                if self.ai_values()!=values:
                    self.feedback(self.ai_result,'配置已更改，请重新验证。')
                    return
            except ValueError:
                self.feedback(self.ai_result,'配置已更改，请重新验证。')
                return
            if error:
                self.feedback(self.ai_result,'验证失败：'+str(error),True)
                return
            if 'models' in result:
                model = self.fields['mjapi_model_select']
                current = model.currentText()
                model.clear()
                model.addItems(result['models'])
                if current in result['models']:
                    model.setCurrentText(current)
            if 'ot_models' in result:
                from bot.akagiot.v3 import model_game
                for key,game in (('akagi_v3_model_4p','4p'),('akagi_v3_model_3p','3p')):
                    control = self.fields[key]
                    current = control.currentText()
                    control.clear()
                    control.addItems(['']+[m['id'] for m in result['ot_models'] if model_game(m)==game])
                    control.setEditText(current)
            self.feedback(self.ai_result,result['message'],result.get('selection_error',False))
        self.owner.run_background(lambda:test_ai_connection(values,fetch_only),complete)

    def _platforms(self,body):
        card = Card()
        for title,detail,status in (
            ('雀魂','对局分析 · MajsoulMax 装扮扩展','已接入'),
            ('一番街','对局适配 · RiichiCityUnlock 接入规划','规划中'),
            ('天凤','对局适配规划','规划中'),
            ('天月麻将 / 掌心麻将','平台与装扮扩展接入规划','规划中')):
            card.body.addWidget(setting_row(title,detail,label(status,'Success' if status=='已接入' else 'Muted')))
        body.addWidget(card)

    def _advanced(self,body):
        card = Card()
        self._switch(card.body,'enable_automation','自动打牌','按 AI 建议执行操作。')
        self._switch(card.body,'auto_join_game','自动加入','按下方房间与模式进入游戏。')
        room = self._combo('auto_join_level',[(name,i) for i,name in enumerate(self.st.lan().GAME_LEVELS)],self.st.auto_join_level)
        card.body.addWidget(setting_row('自动加入房间','',room))
        modes = self._combo('auto_join_mode',list(zip(self.st.lan().GAME_MODES,GAME_MODES)),self.st.auto_join_mode)
        card.body.addWidget(setting_row('对局模式','',modes))
        actions = horizontal()
        actions.addWidget(button('定时停止自动加入',self.owner.show_timer))
        actions.addStretch()
        actions.addWidget(button('保存自动操作',self.save_automation,'Primary'))
        card.body.addLayout(actions)
        self.auto_result = self._result(card.body)
        body.addWidget(card)
        card = Card()
        card.body.addWidget(setting_row('连接与代理','端口、上游代理与浏览器配置。',button('配置 ›',self.owner.show_connection)))
        card.body.addWidget(setting_row('诊断与日志','运行状态、错误详情与日志。',button('查看 ›',self.owner.show_diagnostics)))
        body.addWidget(card)
        extra = button('展开自动操作细节',name='Quiet',checkable=True)
        body.addWidget(extra,0,Qt.AlignLeft)
        details = Card()
        details.setVisible(False)
        extra.toggled.connect(details.setVisible)
        for key,title in (('auto_idle_move','空闲时移动鼠标'),('auto_random_move','随机鼠标移动'),('auto_dahai_drag','拖动出牌')):
            self._switch(details.body,key,title)
        for key,title,minimum,maximum in (('delay_random_lower','操作延时下限（秒）',0,60),('delay_random_upper','操作延时上限（秒）',0,60),('ai_randomize_choice','随机候选范围',0,5),('auto_reply_emoji_rate','表情回复概率',0,1)):
            control = QDoubleSpinBox() if key!='ai_randomize_choice' else QSpinBox()
            control.setRange(minimum,maximum)
            control.setValue(getattr(self.st,key))
            self.fields[key] = control
            details.body.addWidget(setting_row(title,'',control))
        details.body.addWidget(button('保存自动操作细节',self.save_automation))
        body.addWidget(details)

    def save_automation(self):
        keys = ('enable_automation','auto_join_game','auto_join_level','auto_join_mode',
                'auto_idle_move','auto_random_move','auto_dahai_drag','delay_random_lower',
                'delay_random_upper','ai_randomize_choice','auto_reply_emoji_rate')
        values = {}
        for key in keys:
            control = self.fields[key]
            values[key] = control.isChecked() if isinstance(control,Switch) else control.currentData() if isinstance(control,QComboBox) else control.value()
        if values['delay_random_upper'] < values['delay_random_lower']:
            self.feedback(self.auto_result,'延时上限不能小于下限。',True)
            return
        try:
            self.owner.save_settings(values)
            self.feedback(self.auto_result,'自动操作设置已保存。')
        except OSError as error:
            self.feedback(self.auto_result,str(error),True)
