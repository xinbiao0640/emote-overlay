"""全屏透明置顶 overlay：平时点击透传，按热键弹出表情滚轮，选中后弹出表情。"""
import ctypes
import random

from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QGuiApplication, QCursor
from PySide6.QtWidgets import QWidget

from wheel import EmoteWheel, angle_index
from emote import EmoteDisplay
from winutil import hide_taskbar_button

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020


def _init_window_styles(hwnd: int):
    """初始化窗口扩展样式（分层透明 + 不激活 + 点击透传），只调用一次。"""
    user32 = ctypes.windll.user32
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex = ex | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
    user32.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )


def _apply_click_through(hwnd: int, enabled: bool):
    """运行时切换「点击透传」：只翻转 WS_EX_TRANSPARENT，不做 frame 重算（更快）。
    enabled=True 时鼠标点击穿透到下层应用；False 时接收输入（滚轮打开时）。"""
    user32 = ctypes.windll.user32
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if enabled:
        ex = ex | WS_EX_TRANSPARENT
    else:
        ex = ex & ~WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
    user32.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOZORDER,
    )


class Overlay(QWidget):
    def __init__(self, config):
        super().__init__()
        self._groups = list(config.get("groups", []))
        self._group_index = 0
        self._display_cfg = dict(config.get("display", {}))
        self._wheel_cfg = dict(config.get("wheel", {}))

        # 注意：不能用 Qt.Tool，否则会加 WS_EX_TOOLWINDOW，导致 OBS 窗口采集枚举不到。
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        # 标题用于 OBS「窗口采集」枚举到本窗口（无边框下不会显示出来）
        self.setWindowTitle("Emote Overlay")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._monitor_index = int(config.get("display", {}).get("monitor", 0))
        self.setGeometry(self._screen_geometry(self._monitor_index))

        self._wheel = None
        self._wheel_center = None
        self._hover_timer = None
        self._last_emote = None

        self._emote_display = EmoteDisplay(self)
        self._emote_display.setGeometry(self.rect())
        self._emote_display.show()

        self.show()
        self.raise_()
        # 初始状态：点击透传 + 分层透明
        _init_window_styles(int(self.winId()))
        # 隐藏任务栏按钮（等窗口注册后再删）
        QTimer.singleShot(0, lambda: hide_taskbar_button(int(self.winId())))

    # ---- 配置 ----
    def set_groups(self, groups):
        self._groups = list(groups)
        if self._group_index >= len(self._groups):
            self._group_index = 0

    def set_display_cfg(self, cfg):
        self._display_cfg = dict(cfg)

    def set_wheel_cfg(self, cfg):
        self._wheel_cfg = dict(cfg)

    def _screen_geometry(self, index):
        if index < 0:
            return QGuiApplication.primaryScreen().virtualGeometry()
        screens = QGuiApplication.screens()
        if 0 <= index < len(screens):
            return screens[index].geometry()
        return QGuiApplication.primaryScreen().geometry()

    def set_monitor(self, index):
        """把 overlay 限定到指定显示器（用于让 OBS 采集的窗口和该显示器 1:1 对齐）。"""
        self._monitor_index = int(index)
        self.setGeometry(self._screen_geometry(self._monitor_index))
        if self._emote_display is not None:
            self._emote_display.setGeometry(self.rect())

    # ---- 分组 ----
    def _current_emotes(self):
        if 0 <= self._group_index < len(self._groups):
            group = self._groups[self._group_index]
            return group.get("emotes", []) if isinstance(group, dict) else group
        return []

    def _switch_group(self, delta):
        total = len(self._groups)
        if total == 0:
            return
        self._group_index = (self._group_index + delta) % total
        if self._wheel_visible():
            self._wheel.set_emotes(self._current_emotes())
            self._wheel.set_hover_index(-1)

    # ---- 滚轮 ----
    def open_wheel(self):
        if not self._groups:
            return
        if self._wheel_visible():
            return
        emotes = self._current_emotes()
        if not emotes:
            return
        _apply_click_through(int(self.winId()), False)
        self._wheel_center = QCursor.pos()
        self._wheel = EmoteWheel(self, emotes, self._wheel_cfg)
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
        """松开呼出键：选中当前高亮的表情并关闭滚轮。

        若松开时鼠标停在中心（无方向），则重复发送上一个表情，方便连续快速发送。
        """
        if not self._wheel_visible():
            return
        emote = self._wheel.current_emote()
        if emote is None and self._last_emote is not None:
            emote = self._last_emote
        if emote is not None:
            self.show_emote(emote)
            self._last_emote = emote
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
        else:
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
        # 随机小偏移，避免连续发送的表情完全重叠（对所有位置生效）
        x += random.randint(-20, 20)
        y += random.randint(-20, 20)
        return QRect(x, y, size, size)
