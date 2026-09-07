"""全局热键管理，基于 keyboard 库（低层键盘钩子，无需应用获得焦点）。

交互模型：按住呼出键 -> 滚轮出现；松开呼出键 -> 选中并消失。
因此用 on_press_key / on_release_key 分别监听按下与松开。

注意：keyboard 的回调运行在它自己的监听线程里，不能直接在其中创建 QWidget。
这里用 Qt 信号把触发事件安全地转回主线程（跨线程信号会自动走队列连接）。
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
    openPressed = Signal()
    openReleased = Signal()
    dismissTriggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._press_handler = None
        self._release_handler = None
        self._dismiss_handler = None

    def set_hotkeys(self, open_key, dismiss_key):
        self.unbind()
        if open_key:
            try:
                self._press_handler = keyboard.on_press_key(open_key, self._emit_open_pressed)
                self._release_handler = keyboard.on_release_key(open_key, self._emit_open_released)
            except Exception:
                self._press_handler = None
                self._release_handler = None
        if dismiss_key:
            try:
                self._dismiss_handler = keyboard.add_hotkey(dismiss_key, self._emit_dismiss)
            except Exception:
                self._dismiss_handler = None

    def unbind(self):
        for handler in (self._press_handler, self._release_handler):
            if handler is not None:
                try:
                    keyboard.unhook(handler)
                except Exception:
                    pass
        if self._dismiss_handler is not None:
            try:
                keyboard.remove_hotkey(self._dismiss_handler)
            except Exception:
                pass
        self._press_handler = None
        self._release_handler = None
        self._dismiss_handler = None

    def _emit_open_pressed(self, event=None):
        self.openPressed.emit()

    def _emit_open_released(self, event=None):
        self.openReleased.emit()

    def _emit_dismiss(self, *args):
        self.dismissTriggered.emit()
