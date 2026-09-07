"""表情弹出控件：支持静态 PNG 与动态 GIF，带弹出缩放与淡入淡出动画。"""
import os

from PySide6.QtCore import Qt, QRect, QTimer, QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QPainter, QPixmap, QMovie
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect


def is_animated(path):
    ext = os.path.splitext(path)[1].lower()
    return ext == ".gif"


class EmoteDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self._movie = None
        self._pixmap = None
        self._fade_enabled = True

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)

        self._pop_anim = None
        self._fade_in_anim = None
        self._fade_out_anim = None
        self._timer = None
        self.hide()

    def show_emote(self, emote, final_rect: QRect, display_cfg: dict):
        self._clear_animations()
        path = emote.get("file", "")

        if is_animated(path):
            self._movie = QMovie(path)
            self._movie.frameChanged.connect(self.update)
            self._movie.start()
        else:
            self._pixmap = QPixmap(path)
        self._fade_enabled = bool(display_cfg.get("fade", True))

        # 从 0.7 倍大小弹到目标大小（OutBack 回弹）
        f = 0.7
        small = QRect(
            final_rect.x() + int(final_rect.width() * (1 - f) / 2),
            final_rect.y() + int(final_rect.height() * (1 - f) / 2),
            int(final_rect.width() * f),
            int(final_rect.height() * f),
        )
        self.setGeometry(small)
        self.show()
        self.raise_()

        self._pop_anim = QPropertyAnimation(self, b"geometry")
        self._pop_anim.setStartValue(small)
        self._pop_anim.setEndValue(final_rect)
        self._pop_anim.setDuration(220)
        self._pop_anim.setEasingCurve(QEasingCurve.OutBack)
        self._pop_anim.start()

        # 淡入
        if self._fade_enabled:
            self._effect.setOpacity(0.0)
            self._fade_in_anim = QPropertyAnimation(self._effect, b"opacity")
            self._fade_in_anim.setStartValue(0.0)
            self._fade_in_anim.setEndValue(1.0)
            self._fade_in_anim.setDuration(120)
            self._fade_in_anim.start()
        else:
            self._effect.setOpacity(1.0)

        # 定时淡出
        duration = float(display_cfg.get("duration", 2.5))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._timer.start(int(duration * 1000))

    def _fade_out(self):
        if not self.isVisible():
            return
        if not self._fade_enabled:
            self._hide_and_clear()
            return
        self._fade_out_anim = QPropertyAnimation(self._effect, b"opacity")
        self._fade_out_anim.setStartValue(self._effect.opacity())
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setDuration(350)
        self._fade_out_anim.finished.connect(self._hide_and_clear)
        self._fade_out_anim.start()

    def _hide_and_clear(self):
        self.hide()
        self._clear_animations()
        if self._movie is not None:
            self._movie.stop()
            self._movie = None
        self._pixmap = None

    def _clear_animations(self):
        for anim in (self._pop_anim, self._fade_in_anim, self._fade_out_anim):
            if anim is not None:
                anim.stop()
        self._pop_anim = self._fade_in_anim = self._fade_out_anim = None
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self._movie is not None and self._movie.isValid():
            frame = self._movie.currentPixmap()
            if not frame.isNull():
                p.drawPixmap(self.rect(), frame)
        elif self._pixmap is not None and not self._pixmap.isNull():
            p.drawPixmap(self.rect(), self._pixmap)
        p.end()
