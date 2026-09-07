"""表情弹出：每个表情是一个独立的小窗口，支持多个同时显示，带缩放与淡入淡出。"""
import os

from PySide6.QtCore import Qt, QRect, QTimer, QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QPainter, QPixmap, QMovie
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect


def is_animated(path):
    ext = os.path.splitext(path)[1].lower()
    return ext == ".gif"


class _EmoteItem(QWidget):
    """单个表情弹窗，动画结束后自毁。"""

    def __init__(self, emote, display_cfg, on_finished):
        super().__init__()
        self._on_finished = on_finished
        self._movie = None
        self._pixmap = None
        self._fade_enabled = bool(display_cfg.get("fade", True))
        self._duration = float(display_cfg.get("duration", 2.5))

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)

        self._pop_anim = None
        self._fade_in_anim = None
        self._fade_out_anim = None
        self._timer = None

        path = emote.get("file", "")
        if is_animated(path):
            self._movie = QMovie(path)
            self._movie.frameChanged.connect(self.update)
            self._movie.start()
        else:
            self._pixmap = QPixmap(path)

    def start(self, final_rect):
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

        if self._fade_enabled:
            self._effect.setOpacity(0.0)
            self._fade_in_anim = QPropertyAnimation(self._effect, b"opacity")
            self._fade_in_anim.setStartValue(0.0)
            self._fade_in_anim.setEndValue(1.0)
            self._fade_in_anim.setDuration(120)
            self._fade_in_anim.start()
        else:
            self._effect.setOpacity(1.0)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._timer.start(int(self._duration * 1000))

    def _fade_out(self):
        if not self.isVisible():
            return
        if not self._fade_enabled:
            self._finish()
            return
        self._fade_out_anim = QPropertyAnimation(self._effect, b"opacity")
        self._fade_out_anim.setStartValue(self._effect.opacity())
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setDuration(350)
        self._fade_out_anim.finished.connect(self._finish)
        self._fade_out_anim.start()

    def _finish(self):
        self.hide()
        self._clear_animations()
        if self._movie is not None:
            self._movie.stop()
            self._movie = None
        self._pixmap = None
        if self._on_finished is not None:
            self._on_finished(self)

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


class EmoteDisplay(QWidget):
    """表情弹窗管理器：每个表情一个子窗口，可同时显示多个。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._items = []

    def show_emote(self, emote, final_rect, display_cfg):
        item = _EmoteItem(emote, display_cfg, self._on_item_finished)
        item.setParent(self)
        self._items.append(item)
        item.start(final_rect)

    def _on_item_finished(self, item):
        if item in self._items:
            self._items.remove(item)
        item.deleteLater()

    def active_count(self):
        return len(self._items)
