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


def hide_taskbar_button(hwnd):
    """通过 ITaskbarList::DeleteTab 隐藏任务栏按钮。

    这样窗口保持「普通顶层窗口」（可被 OBS 枚举到），同时不出现在任务栏。
    失败时静默忽略（仅多出一个任务栏按钮）。
    """
    try:
        ole32 = ctypes.windll.ole32

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_uint32),
                ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_uint8 * 8),
            ]

        CLSID_TaskbarList = GUID(
            0x56FDF344, 0xFD6D, 0x11D0,
            (ctypes.c_uint8 * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90),
        )
        IID_ITaskbarList = GUID(
            0x56FDF342, 0xFD6D, 0x11D0,
            (ctypes.c_uint8 * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90),
        )

        ole32.CoInitialize(None)
        p = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_TaskbarList), None, 1,
            ctypes.byref(IID_ITaskbarList), ctypes.byref(p),
        )
        if hr != 0 or not p.value:
            return
        vtable = ctypes.cast(p.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
        # ITaskbarList vtable: 0 QI,1 AddRef,2 Release,3 HrInit,4 AddTab,5 DeleteTab,...
        delete_tab = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(vtable[0][5])
        delete_tab(p, wintypes.HWND(hwnd))
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[0][2])
        release(p)
    except Exception:
        pass
