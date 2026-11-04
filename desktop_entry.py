# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Windowed executable entry point and offline installation check."""
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
os.chdir(ROOT)
if getattr(sys, 'frozen', False):
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'


def self_test():
    import asyncio
    import main
    import torch
    import libriichi
    from unittest.mock import patch
    from bot.akagiot.v3 import BotAkagiV3
    from common.utils import GameMode
    from common import utils
    from mjmax.proto import liqi_pb2
    from mitmproxy import options
    from mitmproxy.tools.dump import DumpMaster
    from playwright.sync_api import sync_playwright
    from game.guide_overlay import RENDER_GUIDE
    from bot_manager import BotManager
    from types import SimpleNamespace
    from gui.main_window import MainWindow
    from gui.theme import create_application
    from PySide6.QtWidgets import QLabel
    from common.presentation import advice_rows
    from common.lan_str import LanStrZHS
    from common.settings import Settings
    import tempfile
    MODEL_4P,MODEL_3P = '4p-offline-self-test','3p-offline-self-test'
    # Exercise the frozen adapter with a simulated service; never use saved keys.
    wire_calls = []
    def offline_request(method,url,**kwargs):
        assert kwargs['headers']['Authorization']=='Bearer offline-self-test'
        assert not kwargs['allow_redirects']
        if url.endswith('/v3/key'):
            payload = {'plan':'offline-self-test'}
        elif url.endswith('/v3/models'):
            payload = {'models':[{'id':MODEL_4P,'game':'4p'},{'id':MODEL_3P,'game':'3p'}]}
        else:
            assert method=='POST' and url.endswith('/v3/react')
            body = kwargs['json']
            wire_calls.append(body)
            assert 'can_act' not in body['events'][-1]
            payload = {'model':body['model'],'reaction':{'type':'dahai','actor':body['player_id'],'pai':'1m','tsumogiri':False},
                       'candidates':[{'action':'dahai:1m','prob':.73}]}
        return SimpleNamespace(status_code=200,headers={},json=lambda:payload)
    with patch('bot.akagiot.v3.requests.Session.request',side_effect=offline_request):
        bot = BotAkagiV3('https://offline.invalid','offline-self-test',MODEL_4P,MODEL_3P)
        try:
            for mode,model in ((GameMode.MJ4P,MODEL_4P),(GameMode.MJ3P,MODEL_3P)):
                bot.init_bot(1,mode)
                bot.react({'type':'start_game','id':1})
                bot.react({'type':'start_kyoku','bakaze':'E','dora_marker':'1s','kyoku':1,
                    'honba':0,'kyotaku':0,'oya':1,'scores':[25000]*4,'tehais':[['1m']*13]*4})
                reaction = bot.react({'type':'tsumo','actor':1,'pai':'2m','can_act':True})
                assert wire_calls[-1]['model']==model
                assert reaction['meta_options']==[('1m',.73)]
                assert bot.model_confirmed and bot.last_served_model==model
        finally:
            bot.client.session.close()
    assert libriichi.consts.obs_shape(4)==(1012,34) and libriichi.consts.ACTION_SPACE==46
    with tempfile.TemporaryDirectory() as directory:
        app = create_application()
        setting = Settings(str(Path(directory) / 'settings.json'))
        manager = BotManager(setting)
        root = MainWindow(setting,manager,start_backend=False,register_hotkey=False)
        root.advice_view.set_advice(advice_rows('切🀌六萬',[('🀌六萬',.7),('🀁南',.3)],LanStrZHS()))
        root.show()
        app.processEvents()
        assert root.advice_view.rows[0].findChildren(QLabel)[0].text() == '70%'
        fields = root.settings_page.fields
        fields['model_type'].setCurrentIndex(fields['model_type'].findData('AkagiOT'))
        fields['akagi_ot_protocol'].setCurrentIndex(fields['akagi_ot_protocol'].findData('v3'))
        root.show_settings(1)
        app.processEvents()
        assert fields['akagi_v3_model_4p'].currentText()==''
        assert fields['akagi_v3_model_3p'].currentText()==''
        assert fields['akagi_v3_apikey'].text()==''
        root.settings_page.refresh_model_status(SimpleNamespace(model_confirmed=True,last_served_model=MODEL_3P))
        assert MODEL_3P in root.settings_page.ot_model_status.text()
        root.poll.stop()
        root._shutdown_finished = True
        root.close()
    async def check_proxy():
        master = DumpMaster(options.Options(), with_termlog=False, with_dumper=False)
        master.options.update(stream_large_bodies='256k')
        master.shutdown()
    asyncio.run(check_proxy())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        page.set_content('<title>Copilot packaged browser check</title>')
        assert page.title() == 'Copilot packaged browser check'
        payload = {'id': 'guide-self-test', 'line': 'test', 'options': [],
                   'left': 0, 'top': 0, 'width': 1280, 'height': 720}
        page.evaluate(RENDER_GUIDE, payload)
        card = page.locator('#guide-self-test')
        before = card.bounding_box()
        grip = card.bounding_box()
        page.mouse.move(grip['x'] + grip['width'] / 2, grip['y'] + grip['height'] / 2)
        page.mouse.down()
        page.mouse.move(grip['x'] + grip['width'] / 2 + 100, grip['y'] + grip['height'] / 2)
        page.mouse.up()
        page.evaluate(RENDER_GUIDE, payload)
        assert abs(card.bounding_box()['x'] - before['x'] - 100) < 1
        browser.close()
    manager = BotManager.__new__(BotManager)
    manager.st = SimpleNamespace(enable_automation=False, auto_join_game=False)
    manager.browser = SimpleNamespace(is_page_normal=lambda: True, zoomlevel_check=1.5)
    assert not manager.has_automation_scale_warning()
    manager.st.enable_automation = True
    assert manager.has_automation_scale_warning()
    return {'ok': True, 'torch': torch.__version__, 'rpc_methods': len(liqi_pb2.RPC_METHODS),
            'checks': ['application imports', 'Qt dark desktop', 'protobuf', 'mitmproxy options',
                       'bundled Chromium', 'compact draggable guide', 'new dashboard',
                       'manual mode ignores display scaling','pinned native engine import',
                       'Akagi v3 model selection for both modes (simulated service)',
                       'Akagi v3 frozen settings and actual-model display']}


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        report_path = ROOT / 'log' / 'exe-self-test.json'
        if '--report' in sys.argv:
            report_path = Path(sys.argv[sys.argv.index('--report') + 1]).resolve()
        try:
            report = self_test()
        except Exception:
            report = {'ok': False, 'error': traceback.format_exc()}
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        sys.exit(0 if report['ok'] else 1)
    try:
        from main import main
        main()
    except Exception:
        error_log = ROOT / 'log' / 'desktop-startup-error.log'
        error_log.parent.mkdir(parents=True, exist_ok=True)
        error_log.write_text(traceback.format_exc(), encoding='utf-8')
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f'Startup failed. Details: {error_log}', 'MahjongCopilotPlus', 16)
        sys.exit(1)
