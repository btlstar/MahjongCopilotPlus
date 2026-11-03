# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Qt desktop shell; AI, proxy and game capture keep their existing workers."""
import os
import queue
import threading
import time
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QMainWindow, QWidget, QFrame, QStackedWidget,
    QComboBox, QScrollArea, QLineEdit, QSpinBox, QPlainTextEdit, QApplication)
from bot_manager import mjai_reaction_2_guide
from common.log_helper import LOGGER, LogHelper
from common.presentation import advice_rows
from common.utils import error_to_str, sub_file
from .boss_key import GlobalHotkey, OwnedBrowserWindows
from .theme import GREEN, MUTED, RED, dark_titlebar
from .components import Card, AdviceView, HandView, Switch, QuietDelegate, label, button, column, horizontal, setting_row
from .preferences import SettingsPage, AI_KEYS, valid_url
from .wardrobe import WardrobePage
from .overlays import ModalOverlay


class MainWindow(QMainWindow):
    icon_red,icon_yellow,icon_green,icon_ready = RED,'#d3b87e',GREEN,MUTED

    def __init__(self,setting,bot_manager,*,start_backend=True,register_hotkey=True):
        super().__init__()
        self.st, self.bot_manager = setting, bot_manager
        self._closing = self._shutdown_finished = self._boss_hidden = False
        self._boss_key_available = False
        self._hidden_qt = []
        self._jobs = queue.SimpleQueue()
        self._hotkey = GlobalHotkey() if register_hotkey else None
        self._boss_browser = OwnedBrowserWindows()
        self._modal = None
        self._shutdown_done = threading.Event()
        self._last_hidden_refresh = 0
        self._autojoin_deadline = None
        self._last_rows = []
        self._last_advice = None
        self.setWindowTitle('MahjongCopilotPlus')
        self.resize(*self.st.desktop_size)
        self.setMinimumSize(580,460)
        self._build_shell()
        self.configure_boss_key(self.st.boss_key_enabled,self.st.boss_key)
        dark_titlebar(self)
        self.sync_game_overlay()
        self.poll = QTimer(self)
        self.poll.setInterval(100)
        self.poll.timeout.connect(self._tick)
        self.poll.start()
        if start_backend:
            self.bot_manager.start()
        self._tick()

    def _build_shell(self):
        self.root = QWidget()
        self.root.setObjectName('Root')
        self.setCentralWidget(self.root)
        body = column(self.root,0,0)
        self.nav = QFrame()
        self.nav.setObjectName('Nav')
        nav = horizontal(self.nav,12,5)
        self.nav_buttons = []
        self.pages = QStackedWidget()
        for i,text in enumerate(('对局','装扮','设置')):
            item = button(text,lambda checked=False,index=i:self.show_page(index),'NavButton',True)
            nav.addWidget(item)
            self.nav_buttons.append(item)
        nav.addStretch()
        platform = QComboBox()
        platform.setAccessibleName('游戏平台')
        platform.setItemDelegate(QuietDelegate(platform))
        platform.addItem('雀魂')
        for text in ('一番街','天凤','天月麻将','掌心麻将'):
            platform.addItem(text+' · 规划中')
            platform.model().item(platform.count()-1).setEnabled(False)
        platform.setFixedWidth(122)
        nav.addWidget(platform)
        self.guide_button = button('游戏内提示',self.toggle_game_overlay,'Quiet',True)
        nav.addWidget(self.guide_button)
        self.btn_start_browser = button('打开游戏',self.open_game,'Primary')
        nav.addWidget(self.btn_start_browser)
        body.addWidget(self.nav)
        self._build_game()
        self.wardrobe = WardrobePage(self)
        self.settings_page = SettingsPage(self)
        for page in (self.game_page,self.wardrobe,self.settings_page):
            self.pages.addWidget(page)
        body.addWidget(self.pages,1)
        self.footer = QFrame()
        self.footer.setObjectName('Footer')
        footer = horizontal(self.footer,8,12)
        self.game_status = label('● 雀魂 · 未连接')
        self.ai_status = button('● AI · 未加载',lambda:self.show_settings(1),'Quiet')
        self.ai_status.setStyleSheet('font-size:11px;')
        self.game_status.setStyleSheet('font-size:11px;')
        footer.addWidget(self.game_status)
        footer.addWidget(self.ai_status)
        footer.addStretch()
        footer.addWidget(button('帮助',self.show_help,'Quiet'))
        footer.addWidget(button('诊断',self.show_diagnostics,'Quiet'))
        body.addWidget(self.footer)
        self.show_page(0)

    def _build_game(self):
        self.game_page = QScrollArea()
        self.game_page.setWidgetResizable(True)
        self.game_page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName('Page')
        body = column(content,18,12)
        self.advice_card = Card('AI 建议','等待连接')
        self.advice_view = AdviceView()
        self.advice_card.body.addWidget(self.advice_view)
        body.addWidget(self.advice_card)
        self.hand_card = Card('当前手牌')
        self.hand_view = HandView()
        self.hand_card.body.addWidget(self.hand_view)
        self.hand_card.hide()
        body.addWidget(self.hand_card)
        self.game_notice = label('',wrap=True)
        body.addWidget(self.game_notice)
        body.addStretch()
        self.game_page.setWidget(content)

    def show_page(self,index):
        self.pages.setCurrentIndex(index)
        for i,item in enumerate(self.nav_buttons):
            item.setChecked(i==index)

    def show_settings(self,index=0):
        self.show_page(2)
        self.settings_page.select_tab(index)

    def mainloop(self):
        self.show()
        return QApplication.instance().exec()

    def save_settings(self,changes):
        old = {key:getattr(self.st,key) for key in changes}
        try:
            for key,value in changes.items():
                setattr(self.st,key,value)
            self.st.save_json()
        except Exception:
            for key,value in old.items():
                setattr(self.st,key,value)
            if 'boss_key' in changes:
                self.configure_boss_key(self.st.boss_key_enabled,self.st.boss_key)
            raise
        if any(key in AI_KEYS and old[key]!=value for key,value in changes.items()):
            self.bot_manager.set_bot_update()
        for key,enable,disable in (('enable_automation',self.bot_manager.enable_automation,self.bot_manager.disable_automation),
                                   ('auto_join_game',self.bot_manager.enable_autojoin,self.bot_manager.disable_autojoin)):
            if key in changes and old[key]!=changes[key]:
                (enable if changes[key] else disable)()
        if any(key in changes and old[key]!=changes[key] for key in ('mitm_port','upstream_proxy','enable_proxinject','inject_process_name')):
            self.bot_manager.mitm_proxinject_need_update = True
        if 'enable_overlay' in changes:
            self.sync_game_overlay()
            self.bot_manager.update_overlay()

    def run_background(self,task,complete):
        def run():
            try:
                result,error = task(),None
            except Exception as exc:
                result,error = None,exc
            self._jobs.put((complete,result,error))
        threading.Thread(target=run,name='DesktopTask',daemon=True).start()

    def configure_boss_key(self,enabled,key):
        if self._hotkey is None:
            return True,''
        ok,error = self._hotkey.configure(key if enabled else None)
        if ok:
            self._boss_key_available = bool(enabled)
        self._hotkey_error = error
        return ok,error

    def _toggle_boss_key(self):
        if self._closing or not self._boss_key_available:
            return
        if self._boss_hidden:
            self._restore_boss_windows()
            return
        try:
            self._boss_browser.hide()
        except Exception:
            self._boss_browser.restore()
            LOGGER.exception('Unable to hide owned game browser')
            return
        self._hidden_qt = [(window,window.windowState()) for window in QApplication.topLevelWidgets() if window.isVisible()]
        for window,_ in self._hidden_qt:
            window.hide()
        self._boss_hidden = True

    def _restore_boss_windows(self):
        self._boss_browser.restore()
        for window,state in self._hidden_qt:
            try:
                window.setWindowState(state)
                window.show()
            except RuntimeError:
                pass
        self._hidden_qt = []
        self._boss_hidden = False

    def open_game(self):
        if self.bot_manager.browser.is_running():
            self.bot_manager.browser.bring_to_front()
        elif not self.bot_manager.mitm_proxinject_need_update:
            self.bot_manager.start_browser()

    def toggle_game_overlay(self):
        try:
            self.save_settings({'enable_overlay':not self.st.enable_overlay})
        except OSError:
            self.sync_game_overlay()
            LOGGER.exception('Unable to save game overlay preference')

    def sync_game_overlay(self):
        self.guide_button.setChecked(self.st.enable_overlay)
        self.guide_button.setText('游戏内提示 · 开' if self.st.enable_overlay else '游戏内提示 · 关')
        self.guide_button.setToolTip('开关游戏内 AI 提示；主界面始终保留建议。')
        self.settings_page.sync_game_overlay_choice()

    def _tick(self):
        if self._shutdown_finished:
            return
        try:
            while not self._jobs.empty():
                complete,result,error = self._jobs.get_nowait()
                if not self._closing:
                    complete(result,error)
            if self._hotkey:
                while not self._hotkey.events.empty():
                    self._hotkey.events.get_nowait()
                    self._toggle_boss_key()
            if self._boss_hidden and time.monotonic()-self._last_hidden_refresh > .25:
                self._boss_browser.hide()
                self._last_hidden_refresh = time.monotonic()
            if self._closing:
                if self._shutdown_done.is_set():
                    self._shutdown_finished = True
                    self.close()
                    QApplication.instance().quit()
                return
            if self._autojoin_deadline and time.monotonic()>=self._autojoin_deadline:
                self._autojoin_deadline = None
                self.save_settings({'auto_join_game':False})
                self.settings_page.fields['auto_join_game'].setChecked(False)
            self._refresh_game()
        except Exception:
            LOGGER.exception('Error updating desktop')

    def _refresh_game(self):
        manager = self.bot_manager
        reaction = manager.get_pending_reaction()
        guide,options = mjai_reaction_2_guide(reaction,3,self.st.lan()) if reaction else ('',[])
        signature = (guide,options)
        if signature!=self._last_advice:
            self._last_advice = signature
            self._last_rows = advice_rows(guide,options,self.st.lan()) if guide else []
            self.advice_view.set_advice(self._last_rows)
            self.advice_card.detail.setText('刚刚更新' if guide else '等待 AI 建议' if manager.is_in_game() else '等待连接')
        info = manager.get_game_info()
        hand = info.my_tehai if info and info.my_tehai else []
        self.hand_card.setVisible(bool(hand))
        if hand:
            self.hand_view.set_hand(hand,info.my_tsumohai)
            self.hand_card.detail.setText(f'{self.st.lan().mjai2str(info.bakaze)} {info.kyoku} 局 · {info.honba} 本场')
        state,color = self._status()
        error = manager.main_thread_exception or manager.get_game_error()
        self.game_notice.setText('运行异常，详情见右下角“诊断”。' if error else '')
        self.game_notice.setStyleSheet('color:#e27782;')
        connected = manager.get_game_client_type() is not None
        self.game_status.setText('● 雀魂 · '+('连接异常' if error else '对局中' if manager.is_in_game() else '已连接' if connected else '未连接'))
        game_color = RED if error else GREEN if connected else MUTED
        if getattr(self,'_game_status_color',None)!=game_color:
            self.game_status.setStyleSheet('font-size:11px;color:'+game_color+';')
            self._game_status_color = game_color
        if manager.is_loading_bot:
            ai_text,color = 'AI · 正在加载',MUTED
        elif manager.is_bot_created():
            active = getattr(manager,'active_model_type',None) or manager.bot.name
            active = {'Local':'本地模型','MJAPI':'MJAI'}.get(active,active)
            ai_text,color = active+' · '+('同步中' if manager.is_game_syncing() else '计算中' if manager.is_bot_calculating() else '就绪'),GREEN
            if manager.bot_need_update:
                ai_text += ' · 待切换'
        else:
            ai_text,color = 'AI · 未加载',RED
        self.ai_status.setText('● '+ai_text)
        if getattr(self,'_ai_status_color',None)!=color:
            self.ai_status.setStyleSheet('font-size:11px;color:'+color+';')
            self._ai_status_color = color
        self.ai_status.setMinimumWidth(self.ai_status.fontMetrics().horizontalAdvance(self.ai_status.text())+18)
        running,pending = manager.browser.is_running(),manager.mitm_proxinject_need_update
        self.btn_start_browser.setText('回到游戏' if running else '更新连接中…' if pending else '打开游戏')
        self.btn_start_browser.setEnabled(running or not pending)
        self.btn_start_browser.setToolTip(state)
        if manager.has_automation_scale_warning() and not error:
            self.game_notice.setText(self.st.lan().BROWSER_ZOOM_OFF)
            self.game_notice.setStyleSheet('color:#d3b87e;')
        elif not error and self._hotkey and self.st.boss_key_enabled and not self._boss_key_available:
            self.game_notice.setText('老板键未能注册，请在“设置 → 显示”中更换组合键。')
            self.game_notice.setStyleSheet('color:#d3b87e;')
        manager.update_overlay()

    def _status(self):
        manager = self.bot_manager
        error = manager.main_thread_exception or manager.get_game_error()
        if error:
            return error_to_str(error,self.st.lan()),RED
        if manager.has_automation_scale_warning():
            return self.st.lan().BROWSER_ZOOM_OFF,'#d3b87e'
        return ('对局中' if manager.is_in_game() else '等待游戏'),MUTED

    def _get_status_text_icon(self,gi):
        """Compatibility for callers that still use the old status adapter."""
        manager = self.bot_manager
        error = manager.main_thread_exception or manager.get_game_error()
        if error:
            return error_to_str(error,self.st.lan()),self.icon_red
        if manager.has_automation_scale_warning():
            return self.st.lan().BROWSER_ZOOM_OFF,self.icon_yellow
        return (self.st.lan().GAME_RUNNING,self.icon_green) if manager.is_in_game() else (self.st.lan().READY_FOR_GAME,self.icon_ready)

    def _show_modal(self,title):
        if self._modal:
            self._modal.dismiss()
        modal = self._modal = ModalOverlay(self.root,title)
        for widget in (self.nav,self.pages,self.footer):
            widget.setEnabled(False)
        def closed():
            for widget in (self.nav,self.pages,self.footer):
                widget.setEnabled(True)
            if self._modal is modal:
                self._modal = None
        modal.closed.connect(closed)
        return modal

    def show_connection(self):
        modal = self._show_modal('连接与代理')
        fields = {}
        for key,title in (('mitm_port','代理端口'),('upstream_proxy','上游代理')):
            modal.body.addWidget(label(title))
            item = QLineEdit(str(getattr(self.st,key)))
            item.setObjectName(key)
            item.setPlaceholderText('留空使用直接连接' if key=='upstream_proxy' else '')
            fields[key] = item
            modal.body.addWidget(item)
        extra = button('浏览器与客户端设置 ⌄',name='Quiet',checkable=True)
        modal.body.addWidget(extra,0,Qt.AlignLeft)
        details = QWidget()
        details_body = column(details,0,10)
        url = QLineEdit(self.st.ms_url)
        fields['ms_url'] = url
        details_body.addWidget(label('游戏地址'))
        details_body.addWidget(url)
        modal.body.addWidget(details)
        details.hide()
        def expand(visible):
            details.setVisible(visible)
            modal.reveal()
        extra.toggled.connect(expand)
        for key,title in (('auto_launch_browser','启动时打开游戏'),('browser_resizable','游戏窗口可自由调整大小'),('enable_chrome_ext','加载浏览器扩展'),('enable_proxinject','客户端注入代理')):
            control = Switch(getattr(self.st,key),text=title)
            fields[key] = control
            details_body.addWidget(setting_row(title,'',control))
        size = QWidget()
        layout = horizontal(size)
        for key in ('browser_width','browser_height'):
            control = QSpinBox()
            control.setRange(640 if key.endswith('width') else 360,9999)
            control.setValue(getattr(self.st,key))
            fields[key] = control
            layout.addWidget(control)
        details_body.addWidget(setting_row('初始窗口尺寸','打开后仍可调整。',size))
        result = label('保存后重新打开游戏连接生效。',wrap=True)
        modal.body.addWidget(result)
        actions = horizontal()
        actions.addStretch()
        actions.addWidget(button('取消',modal.dismiss))
        def save():
            try:
                values = {key:control.text().strip() if isinstance(control,QLineEdit) else control.isChecked() if isinstance(control,Switch) else control.value() for key,control in fields.items()}
                if not values['mitm_port'].isdecimal():
                    raise ValueError('代理端口应为 1000–65535 的整数。')
                values['mitm_port'] = int(values['mitm_port'])
                if not self.st.valid_mitm_port(values['mitm_port']):
                    raise ValueError('代理端口应为 1000–65535。')
                if not valid_url(values['ms_url']):
                    raise ValueError('游戏地址须为 http:// 或 https:// URL。')
                if not valid_url(values['upstream_proxy'],optional=True):
                    raise ValueError('上游代理须为 http:// 或 https:// URL。')
                if values['enable_proxinject'] and values['upstream_proxy']:
                    raise ValueError('客户端注入代理不能与上游代理同时开启。')
                if values['enable_proxinject'] and not Path(sub_file('proxinject','proxinjector-cli.exe')).is_file():
                    raise ValueError('请先按安装说明单独准备 proxinject CLI；网页版不需要开启此项。')
                self.save_settings(values)
                modal.dismiss()
            except (ValueError,OSError) as error:
                result.setText(str(error))
                result.setStyleSheet('color:#e27782;')
        actions.addWidget(button('保存配置',save,'Primary'))
        modal.body.addLayout(actions)
        modal.reveal()
        self.connection_fields = fields

    def show_diagnostics(self):
        modal = self._show_modal('诊断与日志')
        modal.body.addWidget(label(self._status()[0],wrap=True))
        error = self.bot_manager.main_thread_exception or self.bot_manager.get_game_error()
        if error:
            modal.body.addWidget(label(str(error),'Error',True))
        if getattr(self,'_hotkey_error',''):
            modal.body.addWidget(label(self._hotkey_error,'Error',True))
        modal.body.addWidget(label('老板键：'+self.st.boss_key+(' · 已注册' if self._boss_key_available else ' · 未启用')))
        log = QPlainTextEdit()
        log.setReadOnly(True)
        log.setMinimumHeight(150)
        path = Path(LogHelper.log_file_name or 'log/no-log')
        if path.is_file():
            with path.open('rb') as stream:
                stream.seek(max(0,path.stat().st_size-16000))
                log.setPlainText(stream.read().decode('utf-8',errors='replace'))
        else:
            log.setPlainText('暂无运行日志。')
        modal.body.addWidget(log)
        if path.is_file():
            modal.body.addWidget(button('打开完整日志',lambda:os.startfile(path)))
        modal.reveal()

    def show_help(self):
        modal = self._show_modal('使用帮助')
        for title,text in (
            ('开始使用','打开游戏并进入牌局。AI 建议与手牌会自动显示。'),
            ('游戏内提示','顶栏开关即时显示或隐藏游戏内提示；整张卡片可拖动，双击或右键复位。主界面始终显示 AI 建议。'),
            ('老板键',self.st.boss_key+' · 隐藏或恢复 Copilot 和它打开的游戏浏览器。'),
            ('退出','使用窗口右上角 X。程序会保存配置并关闭所属浏览器；服务器上的牌局不会因此结束。'),
            ('装扮','MajsoulMax 在游戏内装备。搭配页是参考，不会替你修改当前装扮。')):
            modal.body.addWidget(label(title,'Caption'))
            modal.body.addWidget(label(text,wrap=True))
        modal.reveal()

    def show_timer(self):
        modal = self._show_modal('定时停止自动加入')
        minutes = QSpinBox()
        minutes.setRange(1,1440)
        minutes.setValue(60)
        minutes.setSuffix(' 分钟')
        modal.body.addWidget(setting_row('倒计时','到时只关闭自动加入。',minutes))
        if self._autojoin_deadline:
            modal.body.addWidget(label(f'正在计时，约剩 {max(1,int((self._autojoin_deadline-time.monotonic())/60))} 分钟。'))
        def start():
            self._autojoin_deadline = time.monotonic()+minutes.value()*60
            modal.dismiss()
        actions = horizontal()
        if self._autojoin_deadline:
            def cancel():
                self._autojoin_deadline = None
                modal.dismiss()
            actions.addWidget(button('取消计时',cancel))
        actions.addStretch()
        actions.addWidget(button('开始计时',start,'Primary'))
        modal.body.addLayout(actions)
        modal.reveal()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self._modal:
            self._modal.setGeometry(self.root.rect())
            self._modal.panel.setMaximumHeight(max(150,self.root.height()-32))

    def closeEvent(self,event):
        if self._shutdown_finished:
            event.accept()
            return
        event.ignore()
        if self._closing:
            return
        if self.bot_manager.is_in_game():
            modal = self._show_modal('退出程序')
            modal.body.addWidget(label('退出会关闭本程序打开的游戏浏览器。当前服务器牌局不会因此结束。',wrap=True))
            actions = horizontal()
            actions.addWidget(button('继续对局',modal.dismiss))
            actions.addStretch()
            def confirm():
                modal.dismiss()
                self._begin_shutdown()
            actions.addWidget(button('退出程序',confirm,'Primary'))
            modal.body.addLayout(actions)
            modal.reveal()
        else:
            self._begin_shutdown()

    def _begin_shutdown(self):
        if self._closing:
            return
        self._closing = True
        self.nav.setEnabled(False)
        self.ai_status.setText('正在保存并关闭…')
        if self._boss_hidden:
            self._restore_boss_windows()
        if not self.isMaximized() and not self.isMinimized():
            self.st.desktop_size = [self.width(),self.height()]
        try:
            self.st.save_json()
        except OSError:
            LOGGER.exception('Unable to save settings during shutdown')
        if self._hotkey:
            self._hotkey.close()
        def shutdown():
            try:
                self.bot_manager.stop(True)
            except Exception:
                LOGGER.exception('Unable to stop backend')
            finally:
                self._shutdown_done.set()
        threading.Thread(target=shutdown,name='Shutdown',daemon=True).start()
