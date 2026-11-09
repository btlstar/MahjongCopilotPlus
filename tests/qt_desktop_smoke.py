# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Exercise real Qt controls with temporary configuration and an offline backend."""
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from qt_preview import create_preview,create_application,Settings
from common.log_helper import LOGGER
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton, QLineEdit, QLabel
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parent.parent


def pump(app,seconds=.1):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline:
        app.processEvents()
        time.sleep(.01)


def check_gui():
    LOGGER.setLevel(50)
    app = create_application()
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory() as directory:
        st = Settings(str(Path(directory)/'settings.json'))
        st.model_type = 'AkagiOT'
        st.akagi_ot_protocol = 'legacy'
        st.akagi_ot_url = 'https://example.invalid'
        window = create_preview(st)
        window.show()
        pump(app)
        snapshots = ROOT/'log'/'dark-ui'
        snapshots.mkdir(parents=True,exist_ok=True)
        window.grab().save(str(snapshots/'game.png'))
        assert window.hand_card.isVisible()
        assert [item.text() for item in window.settings_page.tab_buttons]==['显示','AI 连接','连接','自动操作','平台']
        window.show_settings(2)
        pump(app)
        assert not window.settings_page.automation_actions.isVisible()
        assert not window.settings_page.fields['enable_automation'].isVisible()
        window.show_settings(3)
        pump(app)
        page = window.settings_page
        assert page.fields['delay_random_lower'].isVisible()
        assert page.fields['auto_idle_move'].isVisible()
        assert page.automation_actions.isVisible()
        assert not any('展开自动操作细节' in item.text() for item in page.findChildren(QPushButton))
        page.fields['delay_random_lower'].setValue(5)
        page.fields['delay_random_upper'].setValue(2)
        page.save_automation_button.click()
        assert '上限不能小于下限' in page.auto_result.text()
        page.fields['delay_random_upper'].setValue(6)
        page.pages.widget(3).verticalScrollBar().setValue(page.pages.widget(3).verticalScrollBar().maximum())
        pump(app)
        assert page.save_automation_button.isVisible()
        assert page.save_automation_button.geometry().bottom()<=page.automation_actions.height()
        page.save_automation_button.click()
        assert st.delay_random_lower==5 and st.delay_random_upper==6
        assert not st.enable_automation and not st.auto_join_game
        assert '已保存' in page.auto_result.text()
        window.show_settings(1)
        assert not page.automation_actions.isVisible()
        fields = window.settings_page.fields
        provider = fields['model_type']
        provider.setCurrentIndex(provider.findData('Local'))
        pump(app)
        assert fields['model_file'].isVisible() and not fields['akagi_ot_apikey'].isVisible()
        fixture = Path(directory)/'sample.pth'
        fixture.write_bytes(b'offline dialog fixture; not model weights')
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(fixture),'Mortal 模型')):
            browse = fields['model_file'].parentWidget().findChildren(QPushButton)[0]
            QTest.mouseClick(browse,Qt.LeftButton)
        assert fields['model_file'].text()==str(fixture)
        fields['model_file_3p'].clear()
        window.settings_page.save_ai()
        assert st.model_type=='Local' and window.bot_manager.bot_need_update
        window._refresh_game()
        assert 'AkagiOT' in window.ai_status.text() and '待切换' in window.ai_status.text()
        provider.setCurrentIndex(provider.findData('AkagiOT'))
        fields['akagi_ot_apikey'].setText('offline-key')
        secret = fields['akagi_ot_apikey']
        assert secret.echoMode()==QLineEdit.Password
        assert not secret.visibility_action.icon().isNull()
        secret.visibility_action.trigger()
        assert secret.echoMode()==QLineEdit.Normal and secret.text()=='offline-key'
        secret.visibility_action.trigger()
        assert secret.echoMode()==QLineEdit.Password and secret.text()=='offline-key'
        secret.visibility_action.trigger()
        provider.setCurrentIndex(provider.findData('MJAPI'))
        assert secret.echoMode()==QLineEdit.Password
        fields['mjapi_secret'].visibility_action.trigger()
        assert fields['mjapi_secret'].echoMode()==QLineEdit.Normal
        assert fields['mjapi_secret'].isVisible() and not fields['model_file'].isVisible()
        provider.setCurrentIndex(provider.findData('AkagiOT'))
        pump(app)
        assert fields['akagi_ot_apikey'].text()=='offline-key'
        for key in ('akagi_ot_url','akagi_ot_apikey'):
            assert fields[key].height()>=fields[key].sizeHint().height()
        protocol = fields['akagi_ot_protocol']
        protocol.setCurrentIndex(protocol.findData('v3'))
        assert fields['mjapi_secret'].echoMode()==QLineEdit.Password
        pump(app)
        assert fields['akagi_v3_apikey'].isVisible() and not fields['akagi_ot_apikey'].isVisible()
        assert fields['akagi_v3_apikey'].text()==''  # Never copy credentials across services.
        fields['akagi_v3_apikey'].setText('offline-v3-key')
        fields['akagi_v3_apikey'].visibility_action.trigger()
        assert fields['akagi_v3_apikey'].echoMode()==QLineEdit.Normal
        protocol.setCurrentIndex(protocol.findData('legacy'))
        assert fields['akagi_v3_apikey'].echoMode()==QLineEdit.Password
        protocol.setCurrentIndex(protocol.findData('v3'))
        expected = {'4p':'4p-fixture-selected','3p':'3p-fixture-selected'}
        assert fields['akagi_v3_url'].text()=='https://mjapi.shinkuan.me'
        for game in expected:
            assert fields['akagi_v3_model_'+game].currentText()==''
            assert fields['akagi_v3_model_'+game].count()==1
        catalog = [{'id':model,'game':game} for game,model in expected.items()]
        catalog.append({'id':'4p-offline-alternative','game':'4p'})
        def background_fixture(operation,complete):
            complete(operation(),None)
        with patch.object(window,'run_background',side_effect=background_fixture), patch('bot.akagiot.v3.AkagiV3Client.catalog',return_value=catalog):
            window.settings_page.fetch_ot_button.click()
        assert fields['akagi_v3_model_4p'].findText('4p-offline-alternative')>=0
        assert fields['akagi_v3_model_3p'].findText('4p-offline-alternative')<0
        assert '上方下拉框选择' in window.settings_page.ai_result.text()
        window.settings_page.save_ai()
        assert '至少选择' in window.settings_page.ai_result.text()
        for game,model in expected.items():
            control = fields['akagi_v3_model_'+game]
            assert control.currentText()==''
            assert control.findText(model)>=0
            control.setCurrentText(model)
        fields['akagi_v3_model_4p'].setEditText('4p-offline-typed')
        protocol.setCurrentIndex(protocol.findData('legacy'))
        assert fields['akagi_ot_apikey'].text()=='offline-key'
        protocol.setCurrentIndex(protocol.findData('v3'))
        assert fields['akagi_v3_model_4p'].currentText()=='4p-offline-typed'
        fields['akagi_v3_model_4p'].setEditText(expected['4p'])
        window.settings_page.save_ai()
        assert st.akagi_ot_protocol=='v3' and window.bot_manager.bot_need_update
        assert st.akagi_v3_model_4p==expected['4p'] and st.akagi_v3_model_3p==expected['3p']
        page = window.settings_page
        manager = window.bot_manager
        game = manager.game_state
        active = SimpleNamespace(name='offline-active',protocol='v3',
            models={'4p':'4p-current','3p':'3p-current'},model_confirmed=True,last_served_model='4p-current')
        manager.bot = active
        with patch.object(window,'run_background',side_effect=background_fixture), patch('bot.akagiot.v3.AkagiV3Client.catalog',return_value=catalog):
            page.test_button.click()
        assert page.ai_result.text()=='连接与授权检查通过，所选模型可用。'
        window._refresh_game()
        assert '4p-current' in window.model_status.toolTip()
        assert '3p-current' in window.model_status.toolTip()
        assert expected['4p'] not in window.model_status.toolTip()
        assert '4p-current' in window.model_status.text()
        # A completed save replaces its loading text, including deferred loads.
        page.save_ai()
        assert '对局结束后加载' in page.ai_result.text()
        ready = SimpleNamespace(name='offline-ready',protocol='v3',models=expected,
                                model_confirmed=False,supported_modes=[])
        manager.game_state = None
        with patch('bot_manager.get_bot',return_value=ready):
            manager._loop_pre_msg()
        page.refresh_ai_load()
        assert page.ai_result.text()=='AI 已加载并就绪。'
        window._refresh_game()
        assert expected['4p'] in window.model_status.toolTip()
        assert expected['3p'] in window.model_status.toolTip()
        fields['akagi_v3_model_4p'].setEditText('4p-offline-alternative')
        page.save_ai()
        with patch('bot_manager.get_bot',side_effect=ValueError('offline rejected')):
            manager._loop_pre_msg()
        page.refresh_ai_load()
        assert 'AI 加载失败：offline rejected' in page.ai_result.text()
        # Saving unchanged failed settings explicitly retries the load.
        page.save_ai()
        assert manager.bot_need_update
        fields['akagi_v3_model_4p'].setEditText(expected['4p'])
        page.save_ai()
        with patch('bot_manager.get_bot',return_value=ready):
            manager._loop_pre_msg()
        page.refresh_ai_load()
        revision = manager.bot_load_revision
        page.save_ai()
        assert 'AI 已就绪' in page.ai_result.text()
        assert not manager.bot_need_update and manager.bot_load_revision==revision
        # An older background test cannot replace a newer save result.
        pending = []
        with patch.object(window,'run_background',side_effect=lambda task,complete:pending.append(complete)):
            page.test_connection()
        page.save_ai()
        message = page.ai_result.text()
        pending[0]({'message':'obsolete test result'},None)
        assert page.ai_result.text()==message
        # Fetch guidance stays visible even if a saved client finishes loading.
        fields['akagi_v3_model_4p'].setEditText('4p-offline-alternative')
        page.save_ai()
        with patch.object(window,'run_background',side_effect=background_fixture), patch('bot.akagiot.v3.AkagiV3Client.catalog',return_value=catalog):
            page.fetch_ot_button.click()
        message = page.ai_result.text()
        with patch('bot_manager.get_bot',return_value=ready):
            manager._loop_pre_msg()
        page.refresh_ai_load()
        assert page.ai_result.text()==message and '上方下拉框选择' in message
        fields['akagi_v3_model_4p'].setEditText(expected['4p'])
        page.save_ai()
        with patch('bot_manager.get_bot',return_value=ready):
            manager._loop_pre_msg()
        page.refresh_ai_load()
        manager.game_state = game
        labels = '\n'.join(item.text() for item in page.findChildren(QLabel))
        assert all(text not in labels for text in ('不预置型号','当前已加载','推理回报'))
        # Detailed reports and inference errors belong in diagnostics only.
        ready.last_error = 'offline inference error'
        window._refresh_game()
        assert '建议异常' in window.ai_status.text()
        assert 'AI 暂时无法给出建议' in window.game_notice.text()
        window.show_diagnostics()
        details = '\n'.join(item.text() for item in window._modal.findChildren(QLabel))
        assert '尚无模型 ID' in details and 'offline inference error' in details
        assert expected['4p'] in details
        window._modal.dismiss()
        ready.last_error = None
        # Verified models in the footer come from completed inference, not
        # authorization/catalog success. Recent checks remain in diagnostics.
        window.resize(1100,650)
        pump(app)
        ready.mode=SimpleNamespace(value='4P')
        check={'sequence':1,'time':'2026-11-05T12:00:00+08:00','phase':'decision',
               'requested':expected['4p'],'served':expected['4p'],
               'status':'confirmed','elapsed_ms':230}
        ready.last_model_check=check
        ready.model_checks=(check,)
        ready.model_confirmed=True
        ready.last_served_model=expected['4p']
        ready.verified_total,ready.failed_total=1,0
        window._refresh_game()
        assert '已核验' in window.model_status.text()
        assert '通过 1 次' in window.model_status.toolTip()
        window.show_diagnostics()
        from PySide6.QtWidgets import QPlainTextEdit
        audits='\n'.join(item.toPlainText() for item in window._modal.findChildren(QPlainTextEdit))
        assert expected['4p']+' → '+expected['4p'] in audits
        window._modal.dismiss()
        ready.last_model_check=dict(check,status='missing_model',served=None)
        ready.model_confirmed=False
        ready.failed_total=1
        ready.last_error='offline missing model report'
        window._refresh_game()
        assert '未回报模型' in window.model_status.text()
        assert '建议异常' in window.ai_status.text()
        ready.last_model_check=None
        ready.model_checks=()
        ready.last_error=None
        ready.last_served_model=None
        ready.verified_total,ready.failed_total=0,0
        legacy = SimpleNamespace(name='offline-legacy',protocol='legacy',model_confirmed=True,
                                 last_served_model='4p-server-reported')
        manager.bot = legacy
        window._refresh_game()
        assert '旧版 OT · 服务端默认' in window.model_status.toolTip()
        window.show_diagnostics()
        details = '\n'.join(item.text() for item in window._modal.findChildren(QLabel))
        assert '4p-server-reported' in details
        window._modal.dismiss()
        manager.bot = ready
        window.resize(950,800)
        window.settings_page.pages.widget(1).verticalScrollBar().setValue(0)
        pump(app)
        window.grab().save(str(snapshots/'ai.png'))
        window.show_settings(0)
        fields['boss_preset'].setCurrentIndex(fields['boss_preset'].findData('Alt+Z'))
        window.settings_page.save_display()
        assert st.boss_key=='Alt+Z'
        fields['boss_preset'].setCurrentIndex(fields['boss_preset'].findData('custom'))
        fields['boss_key'].setText('Ctrl+Shift+F8')
        window.settings_page.save_display()
        assert st.boss_key=='Ctrl+Shift+F8'
        fields['boss_key'].setText('F12')
        window.settings_page.save_display()
        assert st.boss_key=='Ctrl+Shift+F8'
        window.show_connection()
        modal = window._modal
        assert modal.parentWidget() is window.root and not modal.isWindow()
        old_port = st.mitm_port
        window.connection_fields['mitm_port'].setText('11000')
        modal.dismiss()
        assert st.mitm_port==old_port
        window.show_connection()
        window.connection_fields['mitm_port'].setText('bad')
        next(b for b in window._modal.findChildren(QPushButton) if b.text()=='保存配置').click()
        assert st.mitm_port==old_port and window._modal is not None
        window._modal.dismiss()
        window.show_connection()
        window.connection_fields['mitm_port'].setText('11001')
        pump(app)
        window.grab().save(str(snapshots/'proxy.png'))
        next(b for b in window._modal.findChildren(QPushButton) if b.text()=='保存配置').click()
        assert st.mitm_port==11001 and window.bot_manager.mitm_proxinject_need_update
        assert window._modal is None
        # Disabling an abandoned upstream removes it from the saved route.
        window.save_settings({'upstream_proxy':'http://127.0.0.1:7897'})
        window.show_connection()
        assert window.connection_upstream_switch.isChecked()
        assert window.connection_fields['upstream_proxy'].isEnabled()
        window.connection_upstream_switch.click()
        assert not window.connection_fields['upstream_proxy'].isEnabled()
        window._modal.dismiss()
        assert st.upstream_proxy=='http://127.0.0.1:7897'  # Cancel preserves configuration.
        window.show_connection()
        window.connection_upstream_switch.click()
        next(b for b in window._modal.findChildren(QPushButton) if b.text()=='保存配置').click()
        assert st.upstream_proxy==''
        window.show_diagnostics()
        details = '\n'.join(item.text() for item in window._modal.findChildren(QLabel))
        assert 'Copilot → 游戏服务器（直连）' in details and '7897' not in details
        window._modal.dismiss()
        window.show_help()
        QTest.keyClick(window._modal,Qt.Key_Escape)
        pump(app)
        assert window._modal is None
        # Both controls change the same setting immediately; no second window.
        window.guide_button.click()
        pump(app)
        assert not st.enable_overlay and not fields['enable_overlay'].isChecked()
        fields['enable_overlay'].click()
        assert st.enable_overlay and window.guide_button.isChecked()
        window.show_settings(0)
        window.settings_page.save_display()
        assert st.enable_overlay
        assert not hasattr(window,'floating_window')
        window.show_page(1)
        pump(app)
        window.grab().save(str(snapshots/'wardrobe.png'))
        for width,height in ((580,460),(760,560),(1100,760)):
            window.resize(width,height)
            for index in range(3):
                window.show_page(index)
                pump(app,.03)
                assert window.width()==width
                assert window.model_status.geometry().right() < window.footer.width()
                assert expected['4p'] in window.model_status.toolTip()
                assert expected['3p'] in window.model_status.toolTip()
                if index==2:
                    for tab in range(window.settings_page.pages.count()):
                        window.show_settings(tab)
                        pump(app,.03)
                        assert window.settings_page.pages.currentWidget().horizontalScrollBar().maximum()==0
        window.bot_manager.game_state = None
        window._refresh_game()
        assert not window.hand_card.isVisible()
        window.close()
        deadline = time.monotonic()+5
        while not window._shutdown_finished and time.monotonic()<deadline:
            pump(app,.02)
        assert window._shutdown_finished
        loaded = json.loads(Path(st._json_file).read_text(encoding='utf-8'))
        assert loaded['mitm_port']==11001 and loaded['boss_key']=='Ctrl+Shift+F8'
    return {'ok':True,'checks':['conditional AI forms','native file chooser','provider drafts retained',
        'separate legacy and v3 credentials','mode-specific v3 model catalog','editable model IDs retained',
        'v3 model changes scheduled','inference reports available in diagnostics',
        'secret eye actions preserve text','provider changes conceal secrets','legacy model diagnostics',
        'separate fetch and connection feedback','footer shows loaded model instead of draft',
        'concise settings without duplicate model status','narrow footer preserves full model tooltip',
        'save completion and failure feedback','deferred load completion','unchanged save is ready',
        'failed load can be retried','stale background feedback ignored',
        'actual backend status','two-key presets','invalid hotkey rejected','internal modal',
        'cancel does not save','port validation','proxy reload scheduled','explicit upstream toggle',
        'disabled upstream cleared on save','direct route diagnostics','Esc closes modal',
        'single game-overlay toggle','immediate synchronized settings','empty hand hidden',
        'separate connection and automation tabs','always-visible automation details',
        'persistent automation save feedback and range validation','narrow layout','X shutdown']}


if __name__=='__main__':
    print(json.dumps(check_gui(),ensure_ascii=False))
