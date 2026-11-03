# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Offline Chromium/Qt smoke check; never opens the game or starts a bot."""
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image
from playwright.sync_api import sync_playwright
from game.browser import GameBrowser


def check_browser():
    with sync_playwright() as p:
        chrome = p.chromium.launch(headless=True)
        context = chrome.new_context(viewport={'width': 1280, 'height': 720})
        # Give localStorage a real origin without contacting the network.
        context.route('https://copilot.test/**', lambda route: route.fulfill(
            content_type='text/html',
            body='<canvas id="layaCanvas" style="position:fixed;left:0;top:0;width:100vw;height:100vh"></canvas>'))
        page = context.new_page()
        page.goto('https://copilot.test/')
        browser = GameBrowser(1280, 720)
        browser.page = page
        browser._page_title = 'offline check'
        browser._sync_game_geometry()
        browser._action_start_overlay()
        browser._action_overlay_update_botleft(None)
        def alpha(x, y):
            return page.evaluate('([id,x,y]) => document.getElementById(id).getContext("2d").getImageData(x,y,1,1).data[3]',
                                 [browser._canvas_id, x, y])
        assert alpha(4, 650) == 0
        browser._action_overlay_update_botleft('status')
        assert alpha(4, 650) > 0
        browser._action_overlay_update_botleft(None)
        assert alpha(4, 650) == 0
        browser._action_overlay_update_guide('test', 'options', [('1m', 1.0)])
        guide = page.locator(f'[id="{browser._canvas_id}-guide"]')
        assert guide.is_visible()
        assert 'options' not in guide.inner_text()
        browser._action_overlay_clear_guide()
        assert guide.count() == 0
        browser._action_overlay_update_guide('切🀏九萬', '候选项:',
            [('🀏九萬', 0.24), ('🀁南', 0.19), ('🀡九筒', 0.09)])
        assert guide.locator('[data-guide-row]').count() == 3
        assert guide.locator('[data-guide-probability]').all_text_contents() == ['24%', '19%', '9%']
        assert '候选项' not in guide.inner_text()
        assert guide.inner_text().count('九萬') == 1
        labels = guide.locator('[data-guide-label]').evaluate_all('(nodes) => nodes.map(n => n.getBoundingClientRect().left)')
        percentages = guide.locator('[data-guide-probability]').evaluate_all('(nodes) => nodes.map(n => n.getBoundingClientRect().right)')
        assert max(labels) - min(labels) < 0.1
        assert max(percentages) - min(percentages) < 0.1
        assert guide.evaluate('(node) => getComputedStyle(node).pointerEvents') == 'auto'
        assert guide.inner_text().find('⠿') == -1
        grip = guide
        assert grip.evaluate('(node) => getComputedStyle(node).pointerEvents') == 'auto'
        # The compact card itself receives drag input, avoiding accidental discards.
        page.evaluate("() => { window.gameClicks = 0; document.querySelector('canvas').onclick = () => window.gameClicks++; }")
        label = guide.locator('[data-guide-label]').first.bounding_box()
        page.mouse.click(label['x'] + 5, label['y'] + 5)
        assert page.evaluate('window.gameClicks') == 0
        original = guide.bounding_box()
        handle = grip.bounding_box()
        page.mouse.move(handle['x'] + handle['width'] / 2, handle['y'] + handle['height'] / 2)
        page.mouse.down()
        page.mouse.move(handle['x'] + handle['width'] / 2 + 250, handle['y'] + handle['height'] / 2 - 100, steps=5)
        # An AI update during dragging must not destroy pointer capture.
        browser._action_overlay_update_guide('切🀏九萬', '',
            [('🀏九萬', 0.24), ('🀁南', 0.19), ('🀡九筒', 0.09)])
        assert grip.evaluate('(node) => node.hasPointerCapture(1)')
        page.mouse.move(handle['x'] + handle['width'] / 2 + 300, handle['y'] + handle['height'] / 2 - 100)
        page.mouse.up()
        moved = guide.bounding_box()
        assert abs(moved['x'] - original['x'] - 300) < 1
        assert abs(moved['y'] - original['y'] + 100) < 1
        assert page.evaluate('window.gameClicks') == 0
        saved = page.evaluate("JSON.parse(localStorage.getItem('copilot.guide.position.v1'))")
        assert 0 < saved['x'] < 1 and 0 < saved['y'] < 1
        browser._action_overlay_clear_guide()
        browser._action_overlay_update_guide('切🀏九萬', '',
            [('🀏九萬', 0.24), ('🀁南', 0.19), ('🀡九筒', 0.09)])
        assert abs(guide.bounding_box()['x'] - moved['x']) < 1
        preview = Path(__file__).resolve().parent.parent / 'build/ai-guide-preview.png'
        preview.parent.mkdir(exist_ok=True)
        page.evaluate("document.body.style.background = 'linear-gradient(135deg, #2b3e57, #47617e)'")
        guide.screenshot(path=str(preview))
        browser._action_overlay_update_guide('切🀁南', '',
            [('🀏九萬', 0.24), ('🀁南', 0.19), ('🀡九筒', 0.09)])
        assert guide.locator('[data-guide-probability]').all_text_contents() == ['19%', '24%', '9%']
        page.set_viewport_size({'width': 1000, 'height': 1000})
        page.wait_for_timeout(100)
        browser._sync_game_geometry()
        assert browser.geometry_revision == 1
        assert (browser.width, browser.height, browser.game_top) == (1000, 562.5, 218.75)
        canvas = page.locator(f'[id="{browser._canvas_id}"]').bounding_box()
        assert abs(canvas['y'] - 218.75) < 1
        guide = page.locator(f'[id="{browser._canvas_id}-guide"]')
        assert guide.is_visible()
        assert guide.locator('[data-guide-row]').count() == 3
        box = guide.bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= 1000
        assert box['y'] >= browser.game_top
        assert box['y'] + box['height'] <= browser.game_top + browser.height
        browser._action_stop_overlay()
        page.reload()
        browser._action_start_overlay()
        browser._action_overlay_update_guide('切🀏九萬', '',
            [('🀏九萬', 0.24), ('🀁南', 0.19), ('🀡九筒', 0.09)])
        guide = page.locator(f'[id="{browser._canvas_id}-guide"]')
        assert page.evaluate('window._copilotGuidePosition') == saved
        assert abs(guide.bounding_box()['x'] - box['x']) < 1
        # Double-click reset must clear persistence and restore the default.
        guide.dblclick()
        assert page.evaluate("localStorage.getItem('copilot.guide.position.v1')") is None
        assert abs(guide.bounding_box()['x'] - browser.width * 0.14) < 1
        handle = guide.bounding_box()
        page.mouse.move(handle['x'] + handle['width'] / 2, handle['y'] + handle['height'] / 2)
        page.mouse.down()
        page.mouse.move(5000, 5000)
        page.mouse.up()
        edge = guide.bounding_box()
        assert abs(edge['x'] + edge['width'] - browser.width) < 1
        assert abs(edge['y'] + edge['height'] - browser.game_top - browser.height) < 1
        guide.dblclick()
        browser._action_overlay_update_guide('立直，切🀏九萬（包含很长的操作说明，用于检查换行和边界）', '', [])
        assert guide.evaluate('(node) => node.scrollWidth <= node.clientWidth')
        queue = __import__('queue').Queue()
        browser._action_screen_shot(queue)
        image = Image.open(BytesIO(queue.get()))
        assert image.width == 1000 and abs(image.height - 562.5) <= 1
        browser._action_stop_overlay()
        assert guide.count() == 0
        # Visibility must follow UI state without waiting for a backend loop.
        from bot_manager import BotManager
        from common.lan_str import LanStrZHS
        manager = BotManager.__new__(BotManager)
        manager.browser = browser
        manager.st = SimpleNamespace(enable_overlay=True,show_game_status_overlay=False,lan=LanStrZHS)
        manager.get_pending_reaction = lambda: {'type':'dahai','pai':'6m',
            'meta_options':[('6m',.67),('S',.21),('N',.08)]}
        def drain():
            while not browser._action_queue.empty():
                browser._action_queue.get_nowait()()
        manager.update_overlay()
        drain()
        assert page.locator('[data-guide-row]').count() == 3
        manager.st.enable_overlay = False
        manager.update_overlay()
        drain()
        assert browser._canvas_id is None and page.locator('[data-guide-row]').count() == 0
        # Pending starts/updates must not resurrect a disabled card.
        manager.st.enable_overlay = True
        manager.update_overlay()
        manager.st.enable_overlay = False
        manager.update_overlay()
        drain()
        assert browser._canvas_id is None and page.locator('[data-guide-row]').count() == 0
        manager.st.enable_overlay = True
        manager.update_overlay()
        drain()
        assert page.locator('[data-guide-row]').count() == 3
        manager.st.enable_overlay = False
        manager.update_overlay()
        drain()
        chrome.close()


def check_gui():
    from qt_desktop_smoke import check_gui as check_qt_gui
    return check_qt_gui()


if __name__ == '__main__':
    check_browser()
    check_gui()
    print(json.dumps({'ok': True, 'checks': ['Chromium resizing', 'letterbox coordinates',
        'overlay clear/hide', 'drag during AI update', 'compact card without grip',
        'position persistence/reload/reset', 'cropped screenshots', 'GUI widgets', 'single game-overlay toggle', 'settings dialog']}))
