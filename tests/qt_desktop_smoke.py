# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Exercise real Qt controls with temporary configuration and an offline backend."""
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from qt_preview import create_preview,create_application,Settings
from common.log_helper import LOGGER
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton
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
        st.akagi_ot_url = 'https://example.invalid'
        window = create_preview(st)
        window.show()
        pump(app)
        snapshots = ROOT/'log'/'dark-ui'
        snapshots.mkdir(parents=True,exist_ok=True)
        window.grab().save(str(snapshots/'game.png'))
        assert window.hand_card.isVisible()
        window.show_settings(1)
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
        provider.setCurrentIndex(provider.findData('MJAPI'))
        assert fields['mjapi_secret'].isVisible() and not fields['model_file'].isVisible()
        provider.setCurrentIndex(provider.findData('AkagiOT'))
        pump(app)
        assert fields['akagi_ot_apikey'].text()=='offline-key'
        for key in ('akagi_ot_url','akagi_ot_apikey'):
            assert fields[key].height()>=fields[key].sizeHint().height()
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
                if index==2:
                    for tab in range(4):
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
        'actual backend status','two-key presets','invalid hotkey rejected','internal modal',
        'cancel does not save','port validation','proxy reload scheduled','Esc closes modal',
        'single game-overlay toggle','immediate synchronized settings','empty hand hidden','narrow layout','X shutdown']}


if __name__=='__main__':
    print(json.dumps(check_gui(),ensure_ascii=False))
