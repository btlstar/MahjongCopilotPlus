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
    with tempfile.TemporaryDirectory() as directory:
        app = create_application()
        setting = Settings(str(Path(directory) / 'settings.json'))
        manager = BotManager(setting)
        root = MainWindow(setting,manager,start_backend=False,register_hotkey=False)
        root.advice_view.set_advice(advice_rows('切🀌六萬',[('🀌六萬',.7),('🀁南',.3)],LanStrZHS()))
        root.show()
        app.processEvents()
        assert root.advice_view.rows[0].findChildren(QLabel)[0].text() == '70%'
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
                       'manual mode ignores display scaling']}


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
