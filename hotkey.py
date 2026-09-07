"""全局热键管理，基于 keyboard 库（低层键盘钩子，无需应用获得焦点）。"""
import keyboard
from PySide6.QtCore import QThread, Signal


class KeyCaptureThread(QThread):
    """在后台线程阻塞读取一个按键，用于设置面板里绑定快捷键。"""

    keyCaptured = Signal(str)

    def run(self):
        try:
            key = keyboard.read_key(suppress=True)
            self.keyCaptured.emit(key)
        except Exception:
            self.keyCaptured.emit("")


class HotkeyManager:
    def __init__(self, on_open=None, on_dismiss=None):
        self._on_open = on_open
        self._on_dismiss = on_dismiss
        self._open_handler = None
        self._dismiss_handler = None

    def set_hotkeys(self, open_key, dismiss_key):
        self.unbind()
        if open_key:
            try:
                self._open_handler = keyboard.add_hotkey(open_key, self._safe(self._on_open))
            except Exception:
                self._open_handler = None
        if dismiss_key:
            try:
                self._dismiss_handler = keyboard.add_hotkey(dismiss_key, self._safe(self._on_dismiss))
            except Exception:
                self._dismiss_handler = None

    def unbind(self):
        for handler in (self._open_handler, self._dismiss_handler):
            if handler is not None:
                try:
                    keyboard.remove_hotkey(handler)
                except Exception:
                    pass
        self._open_handler = None
        self._dismiss_handler = None

    @staticmethod
    def _safe(fn):
        """把可能抛异常的回调包装一下，避免钩子线程里异常打断监听。"""
        def wrapper(*args, **kwargs):
            try:
                if fn:
                    fn()
            except Exception:
                pass
        return wrapper
