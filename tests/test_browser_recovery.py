# Modified for MahjongCopilotPlus on 2026-11-04; see NOTICE.md.
"""Refresh and startup failures must retain the owned browser for retry."""
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,MagicMock,patch
from playwright.sync_api import Error

from game.browser import GameBrowser


class BrowserRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.browser = GameBrowser(1280,720)
        self.browser.resizable = False
        self.page = SimpleNamespace(url='https://offline.invalid/',main_frame=object(),
            is_closed=Mock(return_value=False),evaluate=Mock(),close=Mock(),on=Mock(),
            goto=Mock(side_effect=Error('net::ERR_CONNECTION_RESET')))
        self.context = SimpleNamespace(close=Mock(),on=Mock(),pages=[self.page],new_page=Mock())
        self.browser.page,self.browser.context = self.page,self.context
        self.state = {'title':'','ready':True,'zoom':1,'overlay':False}
        self.warning = patch('game.browser.LOGGER.warning')
        self.warning.start()
        self.addCleanup(self.warning.stop)

    def test_destroyed_context_recovers_without_closing_window(self):
        self.page.evaluate.side_effect = [Error('Execution context was destroyed'),self.state]
        self.assertTrue(self.browser._browser_step())
        self.assertFalse(self.browser.is_page_normal())
        self.assertTrue(self.browser.last_page_error)
        self.context.close.assert_not_called()
        self.browser._last_update_time = 0
        self.assertTrue(self.browser._browser_step())
        self.assertTrue(self.browser.is_page_normal())  # Empty titles are valid.
        self.assertIsNone(self.browser.last_page_error)
        self.page.close.assert_not_called()

    def test_only_real_page_or_context_close_ends_worker(self):
        self.page.is_closed.return_value = True
        self.assertFalse(self.browser._browser_step())
        self.page.is_closed.return_value = False
        self.browser._on_context_closed()
        self.assertFalse(self.browser._browser_step())
        self.page.evaluate.assert_not_called()

    def test_failed_start_does_not_leave_a_phantom_overlay_and_can_retry(self):
        self.page.evaluate.side_effect = [Error('Execution context was destroyed'),True]
        self.browser._last_update_time = time.monotonic()
        for _ in range(12):
            self.browser.start_overlay()
        self.assertEqual(self.browser._action_queue.qsize(),1)
        self.assertTrue(self.browser._browser_step())
        self.assertFalse(self.browser.is_overlay_working())
        self.browser.start_overlay()
        self.assertTrue(self.browser._browser_step())
        self.assertTrue(self.browser.is_overlay_working())

    def test_removed_dom_invalidates_cached_advice(self):
        self.browser._canvas_id = 'old'
        self.browser._last_guide = ('unchanged advice','',[],[])
        self.browser._last_botleft_text = 'old'
        self.page.evaluate.return_value = self.state
        self.browser._poll_page()
        self.assertFalse(self.browser.is_overlay_working())
        self.assertIsNone(self.browser._last_guide)
        self.assertIsNone(self.browser._last_botleft_text)
        self.browser._canvas_id = 'intact-canvas'
        self.browser._last_guide = ('same advice','',[],[])
        self.page.evaluate.return_value = dict(self.state,overlay=True,guide=False)
        self.browser._poll_page()
        self.assertEqual(self.browser._canvas_id,'intact-canvas')
        self.assertIsNone(self.browser._last_guide)

    def test_http_502_is_retryable_and_success_clears_error(self):
        response = SimpleNamespace(status=502,frame=self.page.main_frame,
                                   request=SimpleNamespace(is_navigation_request=lambda:True))
        self.page.evaluate.return_value = self.state
        self.browser._on_navigation_response(response)
        self.assertTrue(self.browser._browser_step())
        self.assertIn('502',self.browser.last_page_error)
        self.assertFalse(self.browser.is_page_normal())
        response.status = 200
        self.browser._on_navigation_response(response)
        self.browser._poll_page()
        self.assertTrue(self.browser.is_page_normal())
        self.assertIsNone(self.browser.last_page_error)
        self.context.close.assert_not_called()

    def test_initial_network_failure_and_refresh_race_do_not_exit_runner(self):
        self.page.url = 'about:blank'
        playwright = MagicMock()
        playwright.__enter__.return_value = SimpleNamespace(chromium=SimpleNamespace(
            launch_persistent_context=Mock(return_value=self.context)))
        polls = []
        def poll():
            polls.append(1)
            if len(polls)==1:
                raise Error('Execution context was destroyed during refresh')
            # Simulate an explicit shutdown only after recovery was attempted.
            self.browser._stop_event.set()
        def close():
            self.assertTrue(self.browser._stop_event.is_set())
            self.assertEqual(len(polls),2)
        self.context.close.side_effect = close
        with patch('game.browser.sync_playwright',return_value=playwright), \
             patch('game.browser.utils.sub_folder',return_value=Path('offline-profile')), \
             patch.object(self.browser,'_poll_page',side_effect=poll):
            self.browser._run_browser_and_action_queue('https://offline.invalid/',None)
        self.assertEqual(len(polls),2)
        self.context.close.assert_called_once()


if __name__=='__main__':
    unittest.main()
