# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
import threading
import unittest
from types import SimpleNamespace

from game.browser import GameBrowser
from game.viewport import fit_game_rect
from bot_manager import BotManager
from gui.main_gui import MainGUI
from common.lan_str import LanStr
from common.utils import UiState
from gui.boss_key import parse_hotkey
from common.log_helper import LOGGER


class ViewportTests(unittest.TestCase):
    def test_original_aspect_ratio(self):
        self.assertEqual(fit_game_rect(1280, 720), (0, 0, 1280, 720))

    def test_tall_window_letterbox(self):
        self.assertEqual(fit_game_rect(1000, 1000), (0, 218.75, 1000, 562.5))

    def test_wide_window_letterbox(self):
        self.assertEqual(fit_game_rect(1920, 900), (160, 0, 1600, 900))

    def test_existing_canvas_position(self):
        self.assertEqual(fit_game_rect(1400, 800, {'x': 200, 'y': 100, 'width': 960, 'height': 540}),
                         (200, 100, 960, 540))

    def test_mouse_includes_letterbox_offset(self):
        browser = GameBrowser(1600, 900)
        browser.game_left, browser.game_top = 160, 100
        moves = []
        browser.page = SimpleNamespace(mouse=SimpleNamespace(move=lambda **kwargs: moves.append(kwargs)))
        done = threading.Event()
        browser._action_mouse_move(800, 450, 5, done)
        self.assertTrue(done.is_set())
        self.assertEqual(moves, [{'x': 960, 'y': 550, 'steps': 5}])

    def test_failed_move_releases_waiting_automation_thread(self):
        browser = GameBrowser(1280, 720)
        def closed(**kwargs):
            raise RuntimeError('closed')
        browser.page = SimpleNamespace(mouse=SimpleNamespace(move=closed))
        done = threading.Event()
        with self.assertRaises(RuntimeError):
            browser._action_mouse_move(0, 0, 5, done)
        self.assertTrue(done.is_set())


class ScaleWarningTests(unittest.TestCase):
    def make_manager(self, autoplay=False, autojoin=False, ratio=1.5):
        manager = BotManager.__new__(BotManager)
        manager.st = SimpleNamespace(enable_automation=autoplay, auto_join_game=autojoin)
        manager.browser = SimpleNamespace(is_page_normal=lambda: True, zoomlevel_check=ratio)
        manager.main_thread_exception = None
        manager.game_exception = None
        manager.game_state = None
        manager.automation = SimpleNamespace(ui_state=UiState.NOT_RUNNING)
        return manager

    def test_manual_mode_ignores_display_scaling(self):
        for ratio in (0.8, 1, 1.25, 1.5, 2, None):
            with self.subTest(ratio=ratio):
                self.assertFalse(self.make_manager(ratio=ratio).has_automation_scale_warning())

    def test_warning_only_for_enabled_automatic_actions(self):
        self.assertTrue(self.make_manager(autoplay=True).has_automation_scale_warning())
        self.assertTrue(self.make_manager(autojoin=True).has_automation_scale_warning())
        self.assertFalse(self.make_manager(autoplay=True, ratio=1).has_automation_scale_warning())

    def test_gui_uses_normal_status_without_autoplay(self):
        gui = SimpleNamespace(bot_manager=self.make_manager(),
            st=SimpleNamespace(lan=LanStr), icon_red='red', icon_yellow='yellow',
            icon_green='green', icon_ready='ready')
        text, icon = MainGUI._get_status_text_icon(gui, None)
        self.assertEqual(icon, 'ready')
        self.assertNotEqual(text, LanStr.BROWSER_ZOOM_OFF)
        gui.bot_manager.st.enable_automation = True
        self.assertEqual(MainGUI._get_status_text_icon(gui, None),
                         (LanStr.BROWSER_ZOOM_OFF, 'yellow'))
        # Scaling handling must not suppress a genuine application error.
        gui.bot_manager.main_thread_exception = RuntimeError('test failure')
        self.assertEqual(MainGUI._get_status_text_icon(gui, None)[1], 'red')


class BossKeyTests(unittest.TestCase):
    def test_normalization_and_function_key(self):
        self.assertEqual(parse_hotkey('alt + ctrl + h'), ('Ctrl+Alt+H', 3, ord('H')))
        self.assertEqual(parse_hotkey('Ctrl+Shift+F8'), ('Ctrl+Shift+F8', 6, 0x77))

    def test_reject_bare_keys_duplicates_and_reserved_keys(self):
        for key in ('H', 'Shift+H', 'Ctrl+Ctrl+H', 'Ctrl+F12', 'Win+H', 'Ctrl+Delete', 'Ctrl++H', 'Ctrl+你好'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_hotkey(key)


class ShutdownTests(unittest.TestCase):
    def test_main_loop_failure_still_cleans_all_components(self):
        manager = BotManager.__new__(BotManager)
        calls = []
        def fail():
            raise RuntimeError('startup failed')
        manager._create_mitm_and_proxinject = fail
        manager.automation = SimpleNamespace(stop_previous=lambda: calls.append('automation'))
        manager.browser = SimpleNamespace(stop=lambda join: calls.append('browser'))
        manager.mitm_server = SimpleNamespace(stop=lambda: calls.append('mitm'))
        manager.proxy_injector = SimpleNamespace(stop=lambda join: calls.append('injector'))
        manager.native_tools = SimpleNamespace(stop_unlock=lambda: calls.append('unlock'),stop_capture=lambda: calls.append('native capture'))
        with self.assertLogs(LOGGER, level='ERROR'):
            manager._run()
        self.assertIsInstance(manager.main_thread_exception, RuntimeError)
        self.assertEqual(calls, ['automation', 'browser', 'mitm', 'injector', 'unlock', 'native capture'])

    def test_stop_before_thread_start_is_safe(self):
        manager = BotManager.__new__(BotManager)
        manager._stop_event = threading.Event()
        manager._thread = None
        manager.automation = SimpleNamespace(stop_previous=lambda: None)
        manager.stop(True)
        self.assertTrue(manager._stop_event.is_set())


if __name__ == '__main__':
    unittest.main()
