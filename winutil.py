"""Win32 辅助：检测用户是否正在文本输入，避免热键在打字时误触发。"""
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.c_void_p]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

# 文本编辑控件类名（原生 Edit 与 RichEdit 系列）
EDIT_CLASSES = {
    "Edit",
    "RichEdit",
    "RichEdit20A",
    "RichEdit20W",
    "RichEdit50W",
    "RICHEDIT50W",
    "RICHEDIT60W",
    "ComboBox",
}


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


def _focused_info():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", None
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    user32.GetGUIThreadInfo(tid, ctypes.byref(info))
    focus = info.hwndFocus or hwnd
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(focus, buf, 256)
    return buf.value, info.hwndCaret


def is_typing():
    """当前前台窗口是否处于文本输入状态。"""
    try:
        class_name, caret = _focused_info()
    except Exception:
        return False
    if class_name in EDIT_CLASSES:
        return True
    # 存在可见文本光标也视为正在输入（覆盖浏览器 / Electron 等自绘控件）
    return bool(caret)
