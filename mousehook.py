"""全局鼠标滚轮钩子（WH_MOUSE_LL）：后台线程同步回调，可拦截（抑制）滚轮事件。

与 keyboard 库不同，拦截需要在钩子回调里同步返回 1，因此这里直接用 Win32 底层钩子。
handler(delta) 返回 True 时吞掉该滚轮事件（游戏等其它窗口不再收到），delta 为 +1/-1。
"""
import ctypes
import threading
from ctypes import wintypes

WH_MOUSE_LL = 14
WM_MOUSEWHEEL = 0x020A
WM_QUIT = 0x0012


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


_LowLevelMouseProc = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM,
)

_user32 = ctypes.windll.user32
_user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, _LowLevelMouseProc, ctypes.c_void_p, wintypes.DWORD,
]
_user32.SetWindowsHookExW.restype = ctypes.c_void_p
_user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM,
]
_user32.CallNextHookEx.restype = ctypes.c_long
_user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
_user32.UnhookWindowsHookEx.restype = wintypes.BOOL
_user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
]
_user32.GetMessageW.restype = ctypes.c_int
_user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM,
]
_user32.PostThreadMessageW.restype = wintypes.BOOL


class WheelHook:
    """后台线程安装 WH_MOUSE_LL 钩子，滚轮事件同步回调 handler(delta)->bool。"""

    def __init__(self, handler):
        self._handler = handler
        self._hook = None
        self._proc = None
        self._thread = None

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="wheel-hook")
        self._thread.start()

    def stop(self):
        hook = self._hook
        self._hook = None
        if hook:
            _user32.UnhookWindowsHookEx(hook)
        if self._thread is not None:
            _user32.PostThreadMessageW(self._thread.ident, WM_QUIT, 0, 0)
            self._thread = None

    def _run(self):
        def proc(nCode, wParam, lParam):
            if nCode >= 0 and wParam == WM_MOUSEWHEEL:
                data = ctypes.cast(lParam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents.mouseData
                raw = ctypes.c_short(data >> 16).value
                try:
                    if self._handler(1 if raw > 0 else -1):
                        return 1  # 拦截，其它窗口不再收到该滚轮
                except Exception:
                    pass
            return _user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        self._proc = _LowLevelMouseProc(proc)
        self._hook = _user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, 0, 0)

        # 低层钩子回调靠本线程的消息循环驱动；只需 GetMessage 即可，无需派发到窗口。
        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            pass
