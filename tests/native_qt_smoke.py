# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Native hotkey/visibility/close checks for the Qt desktop, without an account."""
import ctypes
from ctypes import wintypes as wt
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from qt_preview import create_preview,create_application,Settings
from qt_desktop_smoke import pump
from gui.boss_key import GlobalHotkey,Placement
from common.log_helper import LOGGER
from PySide6.QtWidgets import QPushButton
from playwright.sync_api import sync_playwright


def main():
    LOGGER.setLevel(50)
    app = create_application()
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory() as directory, sync_playwright() as p:
        settings = Settings(str(Path(directory)/'settings.json'))
        settings.boss_key = 'Ctrl+Alt+Shift+F11'
        gui = create_preview(settings,register_hotkey=True)
        gui.show()
        second = GlobalHotkey()
        browser = p.chromium.launch(headless=False)
        try:
            page = browser.new_page()
            page.set_content('<title>Copilot offline Qt visibility check</title>')
            pump(app,.4)
            assert gui._boss_key_available
            assert not second.configure(settings.boss_key)[0]
            assert second.configure('Ctrl+Alt+Shift+F10')[0]
            assert not gui.configure_boss_key(True,'Ctrl+Alt+Shift+F10')[0]
            user = ctypes.WinDLL('user32',use_last_error=True)
            user.PostThreadMessageW.argtypes = [wt.DWORD,wt.UINT,wt.WPARAM,wt.LPARAM]
            windows = gui._boss_browser.windows()
            assert windows
            hwnd = windows[0][0]
            assert user.PostThreadMessageW(gui._hotkey.thread.native_id,0x0312,0x4301,0)
            pump(app,.4)
            assert gui._boss_hidden and not gui.isVisible()
            assert not gui._boss_browser.user.IsWindowVisible(hwnd)
            assert page.title()=='Copilot offline Qt visibility check'
            assert user.PostThreadMessageW(gui._hotkey.thread.native_id,0x0312,0x4301,0)
            pump(app,.4)
            assert not gui._boss_hidden and gui.isVisible()
            assert gui._boss_browser.user.IsWindowVisible(hwnd)
            gui._boss_browser.user.ShowWindow(hwnd,3)
            gui.showMaximized()
            gui._toggle_boss_key()
            gui._toggle_boss_key()
            pump(app)
            assert gui.isMaximized()
            placement = Placement()
            placement.length = ctypes.sizeof(placement)
            gui._boss_browser.user.GetWindowPlacement(hwnd,ctypes.byref(placement))
            assert placement.show==3
            # Closing mid-match uses an embedded confirmation, not a native dialog.
            gui.close()
            pump(app)
            assert gui._modal is not None and not gui._closing
            next(b for b in gui._modal.findChildren(QPushButton) if b.text()=='继续对局').click()
            assert gui._modal is None
            gui.bot_manager.game_state = None
            gui.close()
            deadline = time.monotonic()+5
            while not gui._shutdown_finished and time.monotonic()<deadline:
                pump(app,.03)
            assert gui._shutdown_finished and not gui._hotkey.thread.is_alive()
        finally:
            second.close()
            gui._hotkey.close()
            gui._boss_browser.restore()
            gui.poll.stop()
            gui._shutdown_finished = True
            gui.close()
            browser.close()
    print(json.dumps({'ok':True,'checks':['global registration/conflict','message delivery',
        'Qt and Chromium hide/restore','live browser retained','maximized placement',
        'in-window exit confirmation','X shutdown/unregister']}))


if __name__=='__main__':
    main()
