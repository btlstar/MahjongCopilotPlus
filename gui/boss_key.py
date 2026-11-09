# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Windows global hotkey and visibility for this application's own windows.

RegisterHotKey runs on a dedicated message thread; the GUI drains a queue.
No keyboard hook, external dependency, or unrelated browser window is used.
"""
import ctypes
from ctypes import wintypes as wt
import os
import queue
import threading

DEFAULT_HOTKEY = 'Alt+Q'
MODIFIERS = {'CTRL': 2, 'ALT': 1, 'SHIFT': 4}


def parse_hotkey(value):
    """Return a canonical name, Win32 modifiers, and virtual key."""
    parts = [p.strip().upper() for p in value.split('+')]
    if len(parts) < 2 or len(set(parts)) != len(parts):
        raise ValueError('请使用 Ctrl / Alt / Shift + 字母、数字或 F1–F11，例如 Alt+Q。')
    keys = [p for p in parts if p not in MODIFIERS]
    if len(keys) != 1 or not any(p in ('CTRL', 'ALT') for p in parts):
        raise ValueError('老板键需包含 Ctrl 或 Alt，并搭配一个字母、数字或 F1–F11。')
    key = keys[0]
    if len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key)
    elif key.startswith('F') and key[1:].isdigit() and 1 <= int(key[1:]) <= 11:
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError('主键可使用字母、数字或 F1–F11；F12 为系统保留键。')
    mods = sum(MODIFIERS[p] for p in parts if p in MODIFIERS)
    title = '+'.join([p.title() for p in MODIFIERS if p in parts] + [key])
    return title, mods, vk


class GlobalHotkey:
    def __init__(self):
        self.events = queue.Queue()
        self.commands = queue.Queue()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, name='BossKey', daemon=True)
        self.thread.start()

    def configure(self, key):
        parsed = parse_hotkey(key) if key else None
        reply = queue.Queue()
        self.commands.put((parsed, reply))
        try:
            return reply.get(timeout=3)
        except queue.Empty:
            return False, '老板键注册超时，请重试。'

    def close(self):
        self.stopped.set()
        self.thread.join(timeout=2)

    def _run(self):
        if os.name != 'nt':
            while not self.stopped.wait(0.03):
                try:
                    _, reply = self.commands.get_nowait()
                    reply.put((False, '全局老板键仅支持 Windows。'))
                except queue.Empty:
                    pass
            return
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
        user.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
        user.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT]
        active, identity = None, 0x4300
        try:
            while not self.stopped.is_set():
                try:
                    parsed, reply = self.commands.get_nowait()
                    if parsed == active:
                        reply.put((True, ''))
                    elif parsed is None:
                        if active:
                            user.UnregisterHotKey(None, identity)
                        active = None
                        reply.put((True, ''))
                    else:
                        next_id = 0x4301 if identity == 0x4300 else 0x4300
                        if user.RegisterHotKey(None, next_id, parsed[1] | 0x4000, parsed[2]):
                            if active:
                                user.UnregisterHotKey(None, identity)
                            active, identity = parsed, next_id
                            reply.put((True, ''))
                        else:
                            reply.put((False, f'{parsed[0]} 已被占用或无法注册，请更换组合键。'))
                except queue.Empty:
                    pass
                message = wt.MSG()
                while user.PeekMessageW(ctypes.byref(message), None, 0x0312, 0x0312, 1):
                    if active and message.wParam == identity:
                        self.events.put('toggle')
                self.stopped.wait(0.025)
        finally:
            if active:
                user.UnregisterHotKey(None, identity)


class ProcessEntry(ctypes.Structure):
    _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD), ('pid', wt.DWORD),
                ('heap', ctypes.c_size_t), ('module', wt.DWORD), ('threads', wt.DWORD),
                ('parent', wt.DWORD), ('priority', wt.LONG), ('flags', wt.DWORD),
                ('exe', wt.WCHAR * 260)]


class Placement(ctypes.Structure):
    _fields_ = [('length', wt.UINT), ('flags', wt.UINT), ('show', wt.UINT),
                ('minimum', wt.POINT), ('maximum', wt.POINT), ('normal', wt.RECT)]


class OwnedBrowserWindows:
    """Hide/restore only Chrome windows descended from this Copilot process."""
    def __init__(self):
        self.hidden = {}
        if os.name == 'nt':
            self.user = ctypes.WinDLL('user32', use_last_error=True)
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
            self.kernel.CreateToolhelp32Snapshot.restype = wt.HANDLE
            self.kernel.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(ProcessEntry)]
            self.kernel.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(ProcessEntry)]
            self.kernel.CloseHandle.argtypes = [wt.HANDLE]
            self.callback_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
            self.user.EnumWindows.argtypes = [self.callback_type, wt.LPARAM]
            self.user.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
            self.user.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
            self.user.GetWindowPlacement.argtypes = [wt.HWND, ctypes.POINTER(Placement)]
            self.user.SetWindowPlacement.argtypes = [wt.HWND, ctypes.POINTER(Placement)]
            for name in ('IsWindow', 'IsWindowVisible'):
                getattr(self.user, name).argtypes = [wt.HWND]
            self.user.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]

    def descendants(self):
        snapshot = self.kernel.CreateToolhelp32Snapshot(2, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        parents = {}
        try:
            item = ProcessEntry()
            item.dwSize = ctypes.sizeof(item)
            more = self.kernel.Process32FirstW(snapshot, ctypes.byref(item))
            while more:
                parents[item.pid] = item.parent
                more = self.kernel.Process32NextW(snapshot, ctypes.byref(item))
        finally:
            self.kernel.CloseHandle(snapshot)
        owned = {os.getpid()}
        while True:
            children = {pid for pid, parent in parents.items() if parent in owned}
            if children <= owned:
                return owned
            owned.update(children)

    def windows(self):
        if os.name != 'nt':
            return []
        owned = self.descendants()
        windows = []
        @self.callback_type
        def visit(hwnd, _):
            pid = wt.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in owned:
                name = ctypes.create_unicode_buffer(128)
                self.user.GetClassNameW(hwnd, name, len(name))
                if name.value in ('Chrome_WidgetWin_1','UnityWndClass'):
                    windows.append((hwnd, pid.value))
            return True
        self.user.EnumWindows(visit, 0)
        return windows

    def hide(self):
        for hwnd, pid in self.windows():
            if hwnd in self.hidden or not self.user.IsWindowVisible(hwnd):
                continue
            placement = Placement()
            placement.length = ctypes.sizeof(placement)
            if self.user.GetWindowPlacement(hwnd, ctypes.byref(placement)):
                self.hidden[hwnd] = (pid, placement)
                self.user.ShowWindow(hwnd, 0)

    def restore(self):
        for hwnd, (pid, placement) in self.hidden.items():
            current = wt.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(current))
            if self.user.IsWindow(hwnd) and current.value == pid:
                self.user.SetWindowPlacement(hwnd, ctypes.byref(placement))
                self.user.ShowWindow(hwnd, 7 if placement.show == 2 else 8)
        self.hidden.clear()
