"""全屏透明置顶 overlay：平时点击透传，按热键弹出表情滚轮，选中后弹出表情。"""
import ctypes

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QGuiApplication, QCursor
from PySide6.QtWidgets import QWidget

from wheel import EmoteWheel
from emote import EmoteDisplay

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


def _apply_click_through(hwnd: int, enabled: bool):
    """直接改 Win32 扩展样式，运行时可靠地切换「点击透传」。
    enabled=True 时鼠标点击穿透到下层应用；False 时接收输入（滚轮打开时）。"""
    user32 = ctypes.windll.user32
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex = ex | WS_EX_LAYERED | WS_EX_NOACTIVATE
    if enabled:
        ex = ex | WS_EX_TRANSPARENT
    else:
        ex = ex & ~WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
    user32.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )


class Overlay(QWidget):
    def __init__(self, config):
        super().__init__()
        self._emotes = list(config.get("emotes", []))
        self._display_cfg = dict(config.get("display", {}))
        self._wheel_cfg = dict(config.get("wheel", {}))

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        screen = QGuiApplication.primaryScreen()
        self.setGeometry(screen.virtualGeometry())

        self._wheel = None
        self._emote_display = EmoteDisplay(self)

        self.show()
        self.raise_()
        # 初始状态：点击透传
        _apply_click_through(int(self.winId()), True)

    # ---- 配置 ----
    def set_emotes(self, emotes):
        self._emotes = list(emotes)

    def set_display_cfg(self, cfg):
        self._display_cfg = dict(cfg)

    def set_wheel_cfg(self, cfg):
        self._wheel_cfg = dict(cfg)

    # ---- 滚轮 ----
    def open_wheel(self):
        if not self._emotes:
            return
        if self._wheel_visible():
            return
        _apply_click_through(int(self.winId()), False)
        self._wheel = EmoteWheel(self, self._emotes, self._wheel_cfg)
        self._wheel.selected.connect(self._on_wheel_done)
        cursor = QCursor.pos()
        local = self.mapFromGlobal(cursor)
        self._wheel.move(
            int(local.x() - self._wheel.width() / 2),
            int(local.y() - self._wheel.height() / 2),
        )
        self._wheel.show()
        self._wheel.raise_()

    def release_wheel(self):
        """松开呼出键：选中当前高亮的表情并关闭滚轮。"""
        if not self._wheel_visible():
            return
        emote = self._wheel.current_emote()
        if emote is not None:
            self.show_emote(emote)
        self.close_wheel()

    def close_wheel(self):
        if self._wheel is not None:
            self._wheel.hide()
            self._wheel.deleteLater()
            self._wheel = None
        _apply_click_through(int(self.winId()), True)

    def _wheel_visible(self):
        return self._wheel is not None and self._wheel.isVisible()

    def _on_wheel_done(self, emote):
        if emote is not None:
            self.show_emote(emote)
        self.close_wheel()

    def mousePressEvent(self, event):
        # 滚轮打开时点击空白区域 = 取消
        if self._wheel_visible():
            self.close_wheel()

    # ---- 表情弹出 ----
    def show_emote(self, emote):
        rect = self._compute_emote_rect()
        self._emote_display.show_emote(emote, rect, self._display_cfg)

    def _compute_emote_rect(self) -> QRect:
        size = int(self._display_cfg.get("size", 220))
        margin = 40
        w, h = self.width(), self.height()
        pos = self._display_cfg.get("position", "bottom-center")
        x = y = 0
        if pos == "center":
            x, y = (w - size) // 2, (h - size) // 2
        elif pos == "bottom-center":
            x, y = (w - size) // 2, h - size - margin
        elif pos == "top-center":
            x, y = (w - size) // 2, margin
        elif pos == "bottom-left":
            x, y = margin, h - size - margin
        elif pos == "bottom-right":
            x, y = w - size - margin, h - size - margin
        elif pos == "top-left":
            x, y = margin, margin
        elif pos == "top-right":
            x, y = w - size - margin, margin
        return QRect(x, y, size, size)
