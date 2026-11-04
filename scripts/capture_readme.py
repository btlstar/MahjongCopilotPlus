# Modified for MahjongCopilotPlus on 2026-11-04; see NOTICE.md.
"""Capture current Qt/HTML widgets with disposable offline demonstration data.

Run from the repository root: python scripts/capture_readme.py
No backend, account settings, proxy server or global hotkey is started.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_SCALE_FACTOR', '1')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'tests'))
sys.path.insert(0, str(ROOT))

from qt_preview import create_preview, create_application, Settings
from bot_manager import mjai_reaction_2_guide
from common.lan_str import LanStrZHS
from common.log_helper import LOGGER
from common.presentation import advice_rows
from game.guide_overlay import RENDER_GUIDE
from playwright.sync_api import sync_playwright

OUTPUT = ROOT/'assets/screenshots'
MODELS = {'4p':'4p-demo-model', '3p':'3p-demo-model'}


def pump(app):
    deadline = time.monotonic()+.15
    while time.monotonic()<deadline:
        app.processEvents()
        time.sleep(.01)


def capture_desktop():
    LOGGER.setLevel(50)
    app = create_application()
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix='copilot-readme-') as directory:
        st = Settings(str(Path(directory)/'settings.json'))
        st.desktop_size = [900,560]
        st.model_type, st.akagi_ot_protocol = 'AkagiOT', 'v3'
        st.akagi_v3_apikey = 'demo-only-not-a-real-key'
        st.akagi_v3_model_4p, st.akagi_v3_model_3p = MODELS['4p'], MODELS['3p']
        # Never read or alter the user's wardrobe selection or enable flag.
        with patch('gui.wardrobe.expansion_enabled',return_value=True):
            window = create_preview(st)
        manager = window.bot_manager
        manager.bot = SimpleNamespace(name='Offline demonstration',protocol='v3',
                                      models=MODELS,model_confirmed=False)
        manager.mitm_proxinject_need_update = False
        window.show()
        try:
            pump(app)
            window._refresh_game()
            pump(app)
            assert '4p-demo-model' in window.model_status.toolTip()
            assert window.hand_card.isVisible()
            assert window.grab().save(str(OUTPUT/'game.png'))

            window.resize(900,660)
            window.show_settings(1)
            pump(app)
            page = window.settings_page
            assert page.fields['akagi_v3_apikey'].text()==st.akagi_v3_apikey
            assert page.fields['akagi_v3_apikey'].echoMode().name=='Password'
            assert page.fetch_ot_button.isVisible()
            assert page.pages.widget(1).verticalScrollBar().maximum()==0
            assert window.grab().save(str(OUTPUT/'ai.png'))

            window.show_settings(3)
            window.show_connection()
            pump(app)
            assert not window.connection_upstream_switch.isChecked()
            assert st.mitm_port==10999 and st.upstream_proxy==''
            assert window.grab().save(str(OUTPUT/'proxy.png'))
            window._modal.dismiss()

            window.resize(900,560)
            window.show_page(1)
            pump(app)
            assert window.btn_start_browser.text()=='打开游戏'
            assert window.grab().save(str(OUTPUT/'wardrobe.png'))
        finally:
            manager.game_state = None
            window.close()
            deadline = time.monotonic()+5
            while not window._shutdown_finished and time.monotonic()<deadline:
                pump(app)
            assert window._shutdown_finished


def capture_overlay():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True,chromium_sandbox=True)
        try:
            page = browser.new_page(viewport={'width':1280,'height':720},device_scale_factor=2)
            # Block all network requests, including any accidental asset loads.
            page.route('**/*',lambda route:route.abort())
            page.set_content('<body style="margin:0;background:#101113"><canvas id="owner"></canvas></body>')
            line, options = mjai_reaction_2_guide(
                {'type':'dahai','pai':'6m','meta_options':[('6m',.67),('S',.21),('N',.08)]},
                3,LanStrZHS())
            rendered = page.evaluate(RENDER_GUIDE,{
                'id':'readme-guide','ownerId':'owner','line':line,'options':options,
                'left':0,'top':0,'width':1280,'height':720,
                'rows':advice_rows(line,options,LanStrZHS())})
            assert rendered is not False
            card = page.locator('#readme-guide')
            assert card.locator('[data-guide-row]').count()==3
            assert card.locator('[data-guide-tile]').count()==3
            card.screenshot(path=str(OUTPUT/'overlay.png'))
        finally:
            browser.close()


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    with patch('requests.sessions.Session.request',side_effect=RuntimeError('README capture is offline')):
        capture_desktop()
        capture_overlay()
    print(json.dumps({'ok':True,'screenshots':['game.png','ai.png','proxy.png','wardrobe.png','overlay.png'],
                      'data':'offline fixtures; demonstration model IDs; no account credentials'}))


if __name__=='__main__':
    main()
