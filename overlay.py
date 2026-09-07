"""全屏透明置顶 overlay：平时点击透传，按热键弹出表情滚轮，选中后弹出表情。"""
import ctypes
import math
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


def _hide_cursor():
    """把系统光标计数压到 -2 以确保隐藏；多压一层以抵抗一次外部 ShowCursor(True)。"""
    while ctypes.windll.user32.ShowCursor(False) >= -1:
        pass


def _show_cursor():
    """把系统光标计数恢复到非负，重新显示光标。"""
    while ctypes.windll.user32.ShowCursor(True) < 0:
        pass


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("flags", ctypes.c_uint),
                ("hCursor", ctypes.c_void_p), ("ptScreenPos", _POINT)]


def _physical_cursor_pos():
    """返回物理像素坐标下的系统光标位置，与 ClipCursor 同一坐标系（多屏不同 DPI 也能对齐）。"""
    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _cursor_visible():
    """系统光标当前是否可见（GetCursorInfo 的 CURSOR_SHOWING 标志）。"""
    ci = _CURSORINFO()
    ci.cbSize = ctypes.sizeof(_CURSORINFO)
    ctypes.windll.user32.GetCursorInfo(ctypes.byref(ci))
    return bool(ci.flags & 0x00000001)


def _clip_cursor(rect):
    """把系统光标限制在 rect 内（物理像素坐标）；传 None 解除限制。

    ClipCursor 只限制移动范围、不会像 SetCursorPos 那样重新显示光标，
    因此可与 ShowCursor(False) 配合实现「彻底隐藏且不漂移」。
    """
    user32 = ctypes.windll.user32
    if rect is None:
        user32.ClipCursor(None)
        return
    r = _RECT(int(rect.left()), int(rect.top()), int(rect.right()), int(rect.bottom()))
    user32.ClipCursor(ctypes.byref(r))


# 标准系统光标槽位（OCR_*），全部替换成透明光标才能跨窗口彻底隐藏
_OCR_CURSORS = [
    32512,  # OCR_NORMAL
    32513,  # OCR_IBEAM
    32514,  # OCR_WAIT
    32515,  # OCR_CROSS
    32516,  # OCR_UP
    32640,  # OCR_SIZE
    32641,  # OCR_ICON
    32642,  # OCR_SIZENWSE
    32643,  # OCR_SIZENESW
    32644,  # OCR_SIZEWE
    32645,  # OCR_SIZENS
    32646,  # OCR_SIZEALL
    32648,  # OCR_NO
    32649,  # OCR_HAND
    32650,  # OCR_APPSTARTING
]


def _blank_system_cursors():
    """把系统标准光标全部替换为透明光标，实现跨窗口（微信/视频等其它应用）全局隐藏。

    ShowCursor 的隐藏按线程生效，只对本窗口上方生效；透明 overlay 的镂空处命中测试
    会穿透到下层窗口，导致其线程把光标显示出来。因此改用 SetSystemCursor 全局替换。
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    user32.CreateCursor.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
    ]
    user32.CreateCursor.restype = ctypes.c_void_p
    hinst = kernel32.GetModuleHandleW(None)
    # 1x1 单色光标：AND=1（透明）、XOR=0（不画）。每行按 16 位对齐，各占 2 字节。
    and_mask = ctypes.create_string_buffer(b"\xff\xff")
    xor_mask = ctypes.create_string_buffer(b"\x00\x00")
    for ocr in _OCR_CURSORS:
        hcur = user32.CreateCursor(hinst, 0, 0, 1, 1, and_mask, xor_mask)
        if hcur:
            user32.SetSystemCursor(hcur, ocr)


def _restore_system_cursors():
    """SPI_SETCURSORS(0x0057)：从注册表重载系统光标，恢复被替换的默认光标。"""
    ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0)


class Overlay(QWidget):
    def __init__(self, config):
        super().__init__()
        self._groups = list(config.get("groups", []))
        self._group_index = 0
        self._display_cfg = dict(config.get("display", {}))
        self._wheel_cfg = dict(config.get("wheel", {}))
        self._return_cursor = bool(self._display_cfg.get("return_cursor", True))

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
        self._wheel_style = "radial"
        self._cursor_hidden = False

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
        self._return_cursor = bool(cfg.get("return_cursor", True))

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

    def _ensure_nonempty_group(self):
        """若当前分组为空，则前移到下一个非空分组；全空返回 False。"""
        total = len(self._groups)
        if total == 0:
            return False
        for _ in range(total):
            if self._current_emotes():
                return True
            self._group_index = (self._group_index + 1) % total
        return False

    def _switch_group(self, delta):
        total = len(self._groups)
        if total == 0:
            return
        self._group_index = (self._group_index + delta) % total
        self._ensure_nonempty_group()
        if self._wheel_visible():
            self._wheel.set_emotes(self._current_emotes())
            self._wheel.set_hover_index(-1)

    # ---- 滚轮 ----
    def open_wheel(self):
        if not self._groups:
            return
        if self._wheel_visible():
            return
        if not self._ensure_nonempty_group():
            return
        emotes = self._current_emotes()
        _apply_click_through(int(self.winId()), False)
        self._wheel_center = QCursor.pos()
        self._wheel_style = self._wheel_cfg.get("style", "radial")
        if self._wheel_style == "sts2":
            # 隐藏系统光标，改由中心指针指示方向
            QGuiApplication.setOverrideCursor(Qt.BlankCursor)
            self.setCursor(Qt.BlankCursor)
            _hide_cursor()
            _blank_system_cursors()
            self._cursor_hidden = True
            # 限制物理光标在一个小范围内，避免漂移导致光标重新出现。
            # 直接用 GetCursorPos 拿物理像素坐标，多屏 DPI 不一致时也不会把光标错误地
            # 移动到别处（之前用 QCursor.pos()*dpr 换算，在屏幕二会算错导致轮盘错位）。
            px, py = _physical_cursor_pos()
            screen = QGuiApplication.screenAt(self._wheel_center)
            dpr = screen.devicePixelRatio() if screen else 1.0
            rr = int(40 * dpr)
            _clip_cursor(QRect(int(px - rr), int(py - rr), int(rr * 2), int(rr * 2)))
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
        n = self._wheel.slot_count()
        if n == 0:
            return
        if self._wheel_style == "sts2" and self._cursor_hidden:
            # 光标被 ClipCursor 限制在边缘时，系统可能短暂重新显示它；
            # 这里轮询检测，一旦可见立即再隐藏，避免边缘处光标闪现。
            if _cursor_visible():
                _hide_cursor()
        cursor = QCursor.pos()
        dx = cursor.x() - self._wheel_center.x()
        dy = cursor.y() - self._wheel_center.y()
        if self._wheel_style == "sts2":
            self._wheel.set_hover_index(angle_index(dx, dy, n))
            # 中心指针跟随鼠标方向，只限制显示长度；不移动物理光标（SetCursorPos 会导致其重新显示）
            pointer_r = self._wheel.radius * 0.16
            dist = math.hypot(dx, dy)
            if dist > pointer_r:
                k = pointer_r / dist
                dx *= k
                dy *= k
            self._wheel.set_pointer(dx, dy)
        else:
            self._wheel.set_hover_index(angle_index(dx, dy, n))

    def release_wheel(self):
        """松开呼出键：选中当前高亮的表情并关闭滚轮。

        radial 风格下鼠标停在中心（无方向）时重复发送上一个表情，方便连续快速发送。
        sts2 风格下中心指针始终有方向（默认沿用上次），松开即选中对应表情。
        """
        if not self._wheel_visible():
            return
        emote = self._wheel.current_emote()
        if emote is None:
            if self._wheel.hover_index() < 0 and self._last_emote is not None:
                emote = self._last_emote
        if emote is not None:
            self.show_emote(emote)
            self._last_emote = emote
            self.close_wheel(return_cursor=self._return_cursor)
        else:
            self.close_wheel()

    def close_wheel(self, return_cursor=False):
        if self._hover_timer is not None:
            self._hover_timer.stop()
            self._hover_timer = None
        if self._wheel is not None:
            self._wheel.hide()
            self._wheel.deleteLater()
            self._wheel = None
        if self._cursor_hidden:
            # 先恢复形状再显示，避免闪烁；光标留在当前（隐藏追踪）位置
            self.unsetCursor()
            QGuiApplication.restoreOverrideCursor()
            _show_cursor()
            _restore_system_cursors()
            self._cursor_hidden = False
            _clip_cursor(None)
        if return_cursor and self._wheel_center is not None:
            # 选择后将物理光标移回呼出位置（此刻光标已恢复可见，不会闪烁）
            QCursor.setPos(self._wheel_center)
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
        # 表情出现在唤起滚轮时的位置上方，底部距该位置 offset_y 像素
        offset_y = int(self._display_cfg.get("offset_y", 12))
        anchor = self._wheel_center if self._wheel_center is not None else QCursor.pos()
        local = self.mapFromGlobal(anchor)
        x = int(local.x() - size / 2)
        y = int(local.y() - size - offset_y)
        # 随机小偏移，避免连续发送的表情完全重叠
        x += random.randint(-20, 20)
        y += random.randint(-20, 20)
        return QRect(x, y, size, size)
