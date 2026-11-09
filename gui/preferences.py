# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Embedded settings pages; drafts stay separate from running AI state."""
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QStackedWidget, QScrollArea, QLineEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QFileDialog, QSizePolicy)
from common.utils import GAME_MODES, sub_file, Folder
from .boss_key import parse_hotkey
from .components import Card, Switch, QuietDelegate, SecretEdit, label, button, column, horizontal, setting_row

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
            from bot.akagiot.v3 import AkagiV3Client,validate_models,model_game
            client = AkagiV3Client(values['akagi_v3_url'],values['akagi_v3_apikey'])
            try:
                models = client.catalog()
            finally:
                client.session.close()
            if not models:
                raise ValueError('密钥已授权，但没有可用模型。')
            if fetch_only:
                four = sum(model_game(model)=='4p' for model in models)
                three = sum(model_game(model)=='3p' for model in models)
                return {'message':f'已获取 {len(models)} 个可用模型（四麻 {four}／三麻 {three}）。请在上方下拉框选择想用的模型，然后点击“保存配置”。',
                        'ot_models':models}
            validate_models(models,values['akagi_v3_model_4p'],values['akagi_v3_model_3p'])
            selected = any(values[key] for key in ('akagi_v3_model_4p','akagi_v3_model_3p'))
            return {'message':'连接与授权检查通过，所选模型可用。' if selected else '连接与授权检查通过。请选择模型并保存。'}
        from bot.akagiot.http_client import direct_session
        with direct_session() as session:
            response = session.post(values['akagi_ot_url'].rstrip('/')+'/check',
                                    headers={'Authorization':values['akagi_ot_apikey']}, timeout=8)
        response.raise_for_status()
        if response.json().get('result') != 'success':
            raise ValueError('服务未通过授权检查，请检查 API Key。')
        return {'message':'旧版 OT 连接与授权检查通过。'}
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
        self._ai_feedback_ticket = 0
        self._ai_feedback_kind = None
        self._ai_save_pending = None
        self.layout_main = column(self, 18, 14)
        tabs = horizontal(spacing=22)
        self.tab_buttons = []
        self.pages = QStackedWidget()
        for i, text in enumerate(('显示','AI 连接','连接','自动操作','平台')):
            item = button(text, lambda checked=False,index=i:self.select_tab(index), 'Tab', True)
            tabs.addWidget(item)
            self.tab_buttons.append(item)
        tabs.addStretch()
        self.layout_main.addLayout(tabs)
        self.layout_main.addWidget(self.pages,1)
        for builder in (self._display, self._ai, self._connection, self._automation, self._platforms):
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
        self.automation_actions = QWidget()
        actions = horizontal(self.automation_actions,spacing=12)
        self.auto_result = label('',wrap=True)
        actions.addWidget(self.auto_result,1)
        actions.addStretch()
        self.save_automation_button = button('保存自动操作',self.save_automation,'Primary')
        actions.addWidget(self.save_automation_button)
        self.layout_main.addWidget(self.automation_actions)
        self.select_tab(0)

    def select_tab(self, index):
        if index!=1:
            self._conceal_secrets()
        self.pages.setCurrentIndex(index)
        self.automation_actions.setVisible(index==3)
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
        kind = SecretEdit if password else QLineEdit
        entry = kind(str(getattr(self.st,key,'') if value is None else value))
        entry.setObjectName(key)
        entry.setAccessibleName(key)
        self.fields[key] = entry
        return entry

    def _conceal_secrets(self):
        for field in self.fields.values():
            if isinstance(field,SecretEdit):
                field.conceal()

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
        self._switch(card.body,'boss_key_enabled','老板键','隐藏或恢复主界面及本程序启动的游戏窗口。')
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
                        choices = horizontal(spacing=12)
                        for key,title in (('akagi_v3_model_4p','四麻模型'),('akagi_v3_model_3p','三麻模型')):
                            box = QWidget()
                            fields = column(box,0,6)
                            control = self._combo(key,[('','')],getattr(self.st,key))
                            control.setEditable(True)
                            control.lineEdit().setPlaceholderText('获取列表后选择；留空不启用此玩法')
                            control.setMinimumWidth(0)
                            control.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
                            self._field(fields,title,control)
                            choices.addWidget(box,1)
                        form_body.addLayout(choices)
                    else:
                        form_body.addWidget(label('旧版 OT 使用服务端默认模型。',wrap=True))
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
        self.fetch_ot_button = button('获取可用模型',lambda checked=False:self.test_connection(fetch_only=True))
        actions.addWidget(self.fetch_ot_button)
        actions.addStretch()
        actions.addWidget(button('保存配置',self.save_ai,'Primary'))
        card.body.addLayout(actions)
        body.addWidget(card)
        body.addWidget(label('各来源的配置分别保留。对局中保存的 AI 更改会在当前对局结束后加载。',wrap=True))
        self.fields['model_type'].currentIndexChanged.connect(self._provider_changed)
        self._provider_changed()

    def _ot_protocol_changed(self):
        self._conceal_secrets()
        protocol = self.fields['akagi_ot_protocol'].currentData()
        for kind,form in self.ot_forms.items():
            form.setVisible(kind==protocol)
        if hasattr(self,'fetch_ot_button'):
            self._new_ai_feedback('draft')
            self.fetch_ot_button.setVisible(self.fields['model_type'].currentData()=='AkagiOT' and protocol=='v3')
            self.ai_result.clear()

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
        self._conceal_secrets()
        self._new_ai_feedback('draft')
        provider = self.fields['model_type'].currentData()
        for i,page in enumerate(self.ai_provider_pages):
            page.setVisible(i==('AkagiOT','MJAPI','Local').index(provider))
        self.ai_stack.updateGeometry()
        if self.pages.count()>1:
            self.pages.widget(1).verticalScrollBar().setValue(0)
        self.test_button.setText('验证模型' if provider=='Local' else '测试连接')
        self.fetch_ot_button.setVisible(provider=='AkagiOT' and self.fields['akagi_ot_protocol'].currentData()=='v3')
        self.ai_result.clear()

    def ai_values(self,require_model=False):
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
            if require_model and provider=='AkagiOT' and values['akagi_ot_protocol']=='v3' and not any(values[key] for key in ('akagi_v3_model_4p','akagi_v3_model_3p')):
                raise ValueError('请先获取模型列表，并至少选择一个玩法的模型后保存。')
        return values

    def save_ai(self):
        try:
            values = self.ai_values(require_model=True)
            manager = self.owner.bot_manager
            before = getattr(manager,'bot_load_revision',0)
            changed = any(getattr(self.st,key)!=values[key] for key in AI_KEYS)
            previous = self._ai_save_pending
            if values['model_type']=='MJAPI':
                values['mjapi_models'] = [self.fields['mjapi_model_select'].itemText(i) for i in range(self.fields['mjapi_model_select'].count())]
            self.owner.save_settings(values)
            self._new_ai_feedback('save')
            if not changed and not manager.bot_need_update and not manager.is_loading_bot and manager.bot is None:
                manager.set_bot_update()  # Explicit save can retry a failed load.
            if not changed and previous:
                before = previous['before']
            self._ai_save_pending = {'before':before,'values':{key:values[key] for key in AI_KEYS}}
            if not changed and not previous and not manager.bot_need_update and not manager.is_loading_bot and manager.bot is not None:
                self._ai_save_pending = None
                self.feedback(self.ai_result,'配置已保存，AI 已就绪。')
            else:
                self.feedback(self.ai_result,'配置已保存，当前对局结束后加载。' if manager.is_in_game() else '配置已保存，正在加载 AI…')
                self.refresh_ai_load()
        except (ValueError,OSError) as error:
            self._new_ai_feedback('validation')
            self.feedback(self.ai_result,str(error),True)

    def _new_ai_feedback(self,kind):
        self._ai_feedback_ticket += 1
        self._ai_feedback_kind = kind
        return self._ai_feedback_ticket

    def refresh_ai_load(self):
        pending = self._ai_save_pending
        if pending is None:
            return
        manager = self.owner.bot_manager
        failure = manager.main_thread_exception
        worker = getattr(manager,'_thread',None)
        if failure is not None and (worker is None or not worker.is_alive()) and getattr(manager,'bot_load_revision',0)<=pending['before']:
            text,error = 'AI 未能加载：'+str(failure),True
        elif manager.bot_need_update or manager.is_loading_bot or getattr(manager,'bot_load_revision',0)<=pending['before']:
            if self._ai_feedback_kind=='save':
                self.ai_result.setText('配置已保存，当前对局结束后加载。' if manager.is_in_game() and manager.bot_need_update else '配置已保存，正在加载 AI…')
            return
        elif manager.bot is None:
            failure = getattr(manager,'bot_load_error',None) or manager.game_exception
            text,error = 'AI 加载失败：'+str(failure or '未创建可用的 AI，请检查配置后重试。'),True
        else:
            text,error = 'AI 已加载并就绪。',False
        self._ai_save_pending = None
        if self._ai_feedback_kind=='save':
            try:
                current = self.ai_values()
                dirty = any(current[key]!=value for key,value in pending['values'].items())
            except ValueError:
                dirty = True
            if dirty:
                text += '\n表单还有未保存的修改。'
            self.feedback(self.ai_result,text,error)

    def test_connection(self,fetch_only=False):
        try:
            values = self.ai_values()
        except ValueError as error:
            self.feedback(self.ai_result,str(error),True)
            return
        self.test_button.setEnabled(False)
        self.fetch_ot_button.setEnabled(False)
        ticket = self._new_ai_feedback('fetch' if fetch_only else 'test')
        self.ai_result.setText('正在获取可用模型…' if fetch_only else '正在验证模型…' if values['model_type']=='Local' else '正在测试连接…')
        provider = values['model_type']
        def complete(result,error):
            self.test_button.setEnabled(True)
            self.fetch_ot_button.setEnabled(True)
            if ticket!=self._ai_feedback_ticket:
                return
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
                self.feedback(self.ai_result,('获取模型失败：' if fetch_only else '验证失败：')+str(error),True)
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
        self.platform_overview=card
        for title,detail,status in (
            ('雀魂','对局分析 · MajsoulMax 装扮扩展','已接入'),
            ('一番街','原生客户端 · AI 分析与外部 RiichiCityUnlock','实验性接入'),
            ('天凤','对局适配规划','规划中'),
            ('天月麻将 / 掌心麻将','平台与装扮扩展接入规划','规划中')):
            card.body.addWidget(setting_row(title,detail,label(status,'Success' if status=='已接入' else 'Muted')))
        body.addWidget(card)
        native=Card('一番街客户端','实验性接入 · 建议显示在主界面')
        self.native_card=native
        self.native_path_rows={}
        from game.riichicity.tools import NativeTools
        self._field(native.body,'捕获方式',self._combo('riichicity_capture_method',[('进程代理注入（需本地 proxinject）','inject'),('手动进程分流','manual')],self.st.riichicity_capture_method))
        for key,title,filter_ in (('riichicity_injector_path','proxinjector-cli.exe（自动捕获）','Windows 程序 (*.exe)'),
                                  ('riichicity_client_path','游戏本体 exe','Windows 程序 (*.exe)'),
                                  ('riichicity_unlock_path','RiichiCityUnlock.exe','Windows 程序 (*.exe)'),
                                  ('riichicity_unlock_ca','解锁工具 CA（可选）','证书 (*.pem *.cer)')):
            row=QWidget()
            fields=horizontal(row,spacing=8)
            entry=self._entry(key)
            if key=='riichicity_client_path' and not entry.text():
                entry.setText(NativeTools.find_client())
            entry.setPlaceholderText('留空自动使用当前用户 .mitmproxy 的 CA' if key.endswith('_ca') else '')
            fields.addWidget(entry,1)
            def browse(checked=False,control=entry,title=title,filter_=filter_):
                path,_=QFileDialog.getOpenFileName(self,title,control.text(),filter_)
                if path: control.setText(path)
            fields.addWidget(button('浏览…',browse))
            group=QWidget()
            group_body=column(group,0,6)
            self._field(group_body,title,row)
            native.body.addWidget(group)
            self.native_path_rows[key]=group
        port=QSpinBox()
        port.setRange(1000,65535)
        port.setValue(self.st.mitm_port)
        self.fields['riichicity_local_port']=port
        native.body.addWidget(setting_row('Copilot 本地 HTTP 端口','与雀魂共用；客户端应连接此端口。',port))
        unlock=self._switch(native.body,'riichicity_unlock_enabled','同时启用 RiichiCityUnlock','启动本地外部工具；其配置和免费／捐赠模式保持原样。')
        unlock.toggled.connect(self.sync_native_fields)
        self.fields['riichicity_capture_method'].currentIndexChanged.connect(self.sync_native_fields)
        self.native_upstream_row=QWidget()
        upstream_body=column(self.native_upstream_row,0,6)
        self._field(upstream_body,'一番街上游代理（可选）',self._entry('riichicity_upstream_proxy'))
        native.body.addWidget(self.native_upstream_row)
        native.body.addWidget(label('自动捕获仅作用于本程序启动的游戏及其子进程；本机回环连接直连。手动方式可将 Mahjong-JP.exe 的连接通过 Proxifier 等工具指向 127.0.0.1 的 Copilot 端口，代理类型选 HTTPS（HTTP CONNECT）。localhost、127.0.0.1、::1 设为直连。启用解锁时由本地 41110 代理出站。',wrap=True))
        native.body.addWidget(label('当前支持主界面 AI 分析；原生游戏内提示、自动打牌及中途重连恢复尚未接入。',wrap=True))
        self.native_result=self._result(native.body)
        native.body.addWidget(button('保存一番街配置',self.save_native,'Primary'),0,Qt.AlignRight)
        body.addWidget(native)
        self.sync_native_fields()

    def sync_native_fields(self):
        auto=self.fields['riichicity_capture_method'].currentData()=='inject'
        unlock=self.fields['riichicity_unlock_enabled'].isChecked()
        self.native_path_rows['riichicity_injector_path'].setVisible(auto)
        self.native_path_rows['riichicity_unlock_path'].setVisible(unlock)
        self.native_path_rows['riichicity_unlock_ca'].setVisible(unlock)
        self.native_upstream_row.setVisible(not unlock)

    def save_native(self):
        from game.riichicity.tools import NativeTools
        try:
            values={key:self.fields[key].text().strip() for key in ('riichicity_client_path','riichicity_unlock_path','riichicity_unlock_ca','riichicity_upstream_proxy','riichicity_injector_path')}
            values['riichicity_capture_method']=self.fields['riichicity_capture_method'].currentData()
            if values['riichicity_capture_method']=='inject':
                helper=NativeTools.executable(values['riichicity_injector_path'])
                if not (helper.parent/'proxinjectee.dll').is_file(): raise ValueError('代理注入工具目录缺少 proxinjectee.dll。')
            values['riichicity_unlock_enabled']=self.fields['riichicity_unlock_enabled'].isChecked()
            values['mitm_port']=self.fields['riichicity_local_port'].value()
            if values['riichicity_client_path']: NativeTools.executable(values['riichicity_client_path'])
            if values['riichicity_unlock_enabled']:
                NativeTools.executable(values['riichicity_unlock_path'])
                if values['mitm_port']==41110: raise ValueError('Copilot 端口不能与解锁工具的 41110 相同。')
            if values['riichicity_unlock_ca'] and not Path(values['riichicity_unlock_ca']).is_file():
                raise ValueError('所选 CA 证书文件不存在。')
            if values['riichicity_upstream_proxy'] and not valid_url(values['riichicity_upstream_proxy']):
                raise ValueError('一番街上游代理地址格式无效。')
            self.owner.save_settings(values)
            self.owner.wardrobe.sync_platform()
            self.feedback(self.native_result,'已保存；关闭当前游戏客户端后更新连接，捕获方式在下次启动游戏时生效。' if self.owner.bot_manager.is_in_game() else '已保存；捕获方式在下次启动游戏时生效。')
        except (ValueError,OSError) as error:
            self.feedback(self.native_result,str(error),True)

    def sync_platform(self):
        native=self.st.platform=='riichicity'
        self.tab_buttons[3].setVisible(not native)
        self.platform_overview.setVisible(not native)
        self.native_card.setVisible(native)
        for key in ('enable_overlay','show_game_status_overlay'):
            self.fields[key].setEnabled(not native)
            self.fields[key].setToolTip('原生一番街暂仅在主界面显示建议。' if native else '')
        if native and self.pages.currentIndex()==3:
            self.select_tab(0)

    def _connection(self,body):
        card = Card('连接设置')
        card.body.addWidget(setting_row('连接与代理','Copilot 本地端口、游戏上游代理与浏览器配置。',
                                       button('打开连接配置',self.owner.show_connection)))
        body.addWidget(card)
        card = Card('诊断与日志')
        card.body.addWidget(setting_row('运行诊断','查看 AI 错误、模型回报、游戏转发路径与连接状态。',
                                       button('查看诊断',self.owner.show_diagnostics)))
        body.addWidget(card)

    def _automation(self,body):
        card = Card('自动操作','默认关闭')
        self._switch(card.body,'enable_automation','自动打牌','按 AI 建议执行操作。')
        self._switch(card.body,'auto_join_game','自动加入','按下方房间与模式进入游戏。')
        room = self._combo('auto_join_level',[(name,i) for i,name in enumerate(self.st.lan().GAME_LEVELS)],self.st.auto_join_level)
        card.body.addWidget(setting_row('自动加入房间','',room))
        modes = self._combo('auto_join_mode',list(zip(self.st.lan().GAME_MODES,GAME_MODES)),self.st.auto_join_mode)
        card.body.addWidget(setting_row('对局模式','',modes))
        card.body.addWidget(button('定时停止自动加入',self.owner.show_timer),0,Qt.AlignLeft)
        body.addWidget(card)
        details = Card('操作细节','鼠标行为与执行节奏')
        for key,title in (('auto_idle_move','空闲时移动鼠标'),('auto_random_move','随机鼠标移动'),('auto_dahai_drag','拖动出牌')):
            self._switch(details.body,key,title)
        for key,title,minimum,maximum in (('delay_random_lower','操作延时下限（秒）',0,60),('delay_random_upper','操作延时上限（秒）',0,60),('ai_randomize_choice','随机候选范围',0,5),('auto_reply_emoji_rate','表情回复概率',0,1)):
            control = QDoubleSpinBox() if key!='ai_randomize_choice' else QSpinBox()
            control.setRange(minimum,maximum)
            control.setValue(getattr(self.st,key))
            self.fields[key] = control
            details.body.addWidget(setting_row(title,'',control))
        body.addWidget(details)

    def save_automation(self):
        if self.st.platform!='majsoul':
            self.feedback(self.auto_result,'一番街当前仅支持 AI 分析。',True)
            return
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
