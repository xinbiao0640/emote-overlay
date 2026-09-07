"""全局热键管理，基于 keyboard 库（低层键盘钩子，无需应用获得焦点）。

注意：keyboard 的回调运行在它自己的监听线程里，不能直接在其中创建 QWidget。
因此这里用 Qt 信号把触发事件安全地转回主线程（跨线程信号会自动走队列连接）。
"""
import keyboard
from PySide6.QtCore import QObject, QThread, Signal


class KeyCaptureThread(QThread):
    """在后台线程阻塞读取一个按键，用于设置面板里绑定快捷键。"""

    keyCaptured = Signal(str)

    def run(self):
        try:
            key = keyboard.read_key(suppress=True)
            self.keyCaptured.emit(key)
        except Exception:
            self.keyCaptured.emit("")


class HotkeyManager(QObject):
    openTriggered = Signal()
    dismissTriggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._open_handler = None
        self._dismiss_handler = None

    def set_hotkeys(self, open_key, dismiss_key):
        self.unbind()
        if open_key:
            try:
                self._open_handler = keyboard.add_hotkey(open_key, self.openTriggered.emit)
            except Exception:
                self._open_handler = None
        if dismiss_key:
            try:
                self._dismiss_handler = keyboard.add_hotkey(dismiss_key, self.dismissTriggered.emit)
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
