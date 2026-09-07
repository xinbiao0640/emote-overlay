"""全屏透明置顶 overlay：平时点击透传，按热键弹出表情滚轮，选中后弹出表情。"""
import ctypes

from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QGuiApplication, QCursor
from PySide6.QtWidgets import QWidget

from wheel import EmoteWheel, angle_index
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
        self._groups = list(config.get("groups", []))
        self._group_index = 0
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
        self._wheel_center = None
        self._hover_timer = None
        self._emote_display = EmoteDisplay(self)

        self.show()
        self.raise_()
        # 初始状态：点击透传
        _apply_click_through(int(self.winId()), True)

    # ---- 配置 ----
    def set_groups(self, groups):
        self._groups = list(groups)
        if self._group_index >= len(self._groups):
            self._group_index = 0

    def set_display_cfg(self, cfg):
        self._display_cfg = dict(cfg)

    def set_wheel_cfg(self, cfg):
        self._wheel_cfg = dict(cfg)

    # ---- 分组 ----
    def _current_emotes(self):
        if 0 <= self._group_index < len(self._groups):
            group = self._groups[self._group_index]
            return group.get("emotes", []) if isinstance(group, dict) else group
        return []

    def _current_label(self):
        if 0 <= self._group_index < len(self._groups):
            group = self._groups[self._group_index]
            if isinstance(group, dict):
                return group.get("name", "")
        return ""

    def _switch_group(self, delta):
        total = len(self._groups)
        if total == 0:
            return
        self._group_index = (self._group_index + delta) % total
        if self._wheel_visible():
            self._wheel.set_emotes(self._current_emotes())
            self._wheel.set_group_label(self._current_label())
            self._wheel.set_hover_index(-1)

    # ---- 滚轮 ----
    def open_wheel(self):
        if not self._groups:
            return
        if self._wheel_visible():
            return
        self._group_index = 0
        emotes = self._current_emotes()
        if not emotes:
            return
        _apply_click_through(int(self.winId()), False)
        self._wheel_center = QCursor.pos()
        self._wheel = EmoteWheel(self, emotes, self._wheel_cfg, self._current_label())
        cursor = QCursor.pos()
        local = self.mapFromGlobal(cursor)
        self._wheel.move(
            int(local.x() - self._wheel.width() / 2),
            int(local.y() - self._wheel.height() / 2),
        )
        self._wheel.show()
        self._wheel.raise_()
        # 用定时器轮询鼠标位置，按「方向角度」更新高亮，不限制移动距离
        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self._update_hover)
        self._hover_timer.start(16)

    def wheelEvent(self, event):
        # 滚轮打开时，鼠标滚轮用于切换表情分组
        if not self._wheel_visible():
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self._switch_group(1)
        elif delta < 0:
            self._switch_group(-1)
        event.accept()

    def _update_hover(self):
        if not self._wheel_visible():
            return
        emotes = self._current_emotes()
        n = len(emotes)
        if n == 0:
            return
        cursor = QCursor.pos()
        dx = cursor.x() - self._wheel_center.x()
        dy = cursor.y() - self._wheel_center.y()
        self._wheel.set_hover_index(angle_index(dx, dy, n))

    def release_wheel(self):
        """松开呼出键：选中当前高亮的表情并关闭滚轮。"""
        if not self._wheel_visible():
            return
        emote = self._wheel.current_emote()
        if emote is not None:
            self.show_emote(emote)
        self.close_wheel()

    def close_wheel(self):
        if self._hover_timer is not None:
            self._hover_timer.stop()
            self._hover_timer = None
        if self._wheel is not None:
            self._wheel.hide()
            self._wheel.deleteLater()
            self._wheel = None
        _apply_click_through(int(self.winId()), True)

    def _wheel_visible(self):
        return self._wheel is not None and self._wheel.isVisible()

    def mousePressEvent(self, event):
        # 滚轮打开时点击空白区域 = 取消
        if self._wheel_visible():
            self.close_wheel()

    # ---- 表情弹出 ----
    def show_emote(self, emote):
        rect = self._compute_emote_rect()
        self._emote_display.show_emote(emote, rect, self._display_cfg)

    def _compute_emote_rect(self) -> QRect:
        size = int(self._display_cfg.get("size", 120))
        margin = 40
        w, h = self.width(), self.height()
        pos = self._display_cfg.get("position", "cursor")
        if pos == "cursor":
            local = self.mapFromGlobal(QCursor.pos())
            x = int(local.x() - size / 2)
            y = int(local.y() - size / 2)
            return QRect(x, y, size, size)
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
