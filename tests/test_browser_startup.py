# Modified for MahjongCopilotPlus on 2026-11-04; see NOTICE.md.
"""Startup should reuse a blank tab without replacing restored user content."""
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
from game.browser import GameBrowser


def page(url,closed=False):
    return SimpleNamespace(url=url,is_closed=lambda:closed,goto=Mock(),on=Mock())


class StartupPageTests(unittest.TestCase):
    def test_existing_blank_page_is_used_without_new_tab(self):
        for url in ('about:blank','chrome://newtab/','chrome://new-tab-page/'):
            with self.subTest(url=url):
                initial = page(url)
                browser = GameBrowser(1280,720)
                browser.context = SimpleNamespace(pages=[initial],new_page=Mock(),on=Mock())
                browser._open_initial_page('https://game.example.invalid/')
                self.assertIs(browser.page,initial)
                browser.context.new_page.assert_not_called()
                initial.goto.assert_called_once_with('https://game.example.invalid/',wait_until='domcontentloaded')

    def test_restored_content_is_preserved(self):
        restored,new = page('https://saved.example.invalid/'),page('about:blank')
        browser = GameBrowser(1280,720)
        browser.context = SimpleNamespace(pages=[restored],new_page=Mock(return_value=new),on=Mock())
        browser._open_initial_page('https://game.example.invalid/')
        restored.goto.assert_not_called()
        self.assertIs(browser.page,new)

    def test_closed_blank_tabs_are_not_reused(self):
        closed,new = page('about:blank',True),page('about:blank')
        browser = GameBrowser(1280,720)
        browser.context = SimpleNamespace(pages=[closed],new_page=Mock(return_value=new),on=Mock())
        browser._open_initial_page('https://game.example.invalid/')
        self.assertIs(browser.page,new)
        closed.goto.assert_not_called()


if __name__=='__main__':
    unittest.main()
