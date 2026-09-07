"""径向表情滚轮：围绕圆心分布表情，高亮索引由 overlay 按鼠标方向角度驱动。"""
import math
import os

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QMovie
from PySide6.QtWidgets import QWidget


def _thumbnail(emote):
    """GIF 取第一帧做缩略图，PNG/WebP 直接加载。"""
    path = emote.get("file", "")
    if os.path.splitext(path)[1].lower() == ".gif":
        movie = QMovie(path)
        if movie.isValid():
            movie.jumpToFrame(0)
            pm = movie.currentPixmap()
            movie.stop()
            return pm
    return QPixmap(path)


def angle_index(dx, dy, n, inner_radius):
    """根据鼠标相对滚轮中心的方向向量，计算高亮的表情索引。

    只看方向角度、不限制距离：只要离开中心死区（inner_radius），
    移动多远都能选中对应方向的表情。死区内返回 -1。
    """
    if n == 0 or math.hypot(dx, dy) <= inner_radius:
        return -1
    theta = math.degrees(math.atan2(dx, -dy))
    if theta < 0:
        theta += 360.0
    return int(theta // (360.0 / n)) % n


class EmoteWheel(QWidget):
    def __init__(self, parent, emotes, wheel_cfg):
        super().__init__(parent)
        self.emotes = list(emotes)
        self.radius = int(wheel_cfg.get("radius", 130))
        self.inner_radius = int(wheel_cfg.get("inner_radius", 25))
        self._hover_index = -1

        self.setAttribute(Qt.WA_TranslucentBackground)

        padding = 20
        size = (self.radius + padding) * 2
        self.resize(size, size)
        self._center = QPointF(self.width() / 2, self.height() / 2)

        self._pixmaps = [_thumbnail(e) for e in self.emotes]

    def set_hover_index(self, idx):
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()

    def current_emote(self):
        """返回当前高亮的表情，未高亮则返回 None。"""
        if 0 <= self._hover_index < len(self.emotes):
            return self.emotes[self._hover_index]
        return None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(self.emotes)
        if n == 0:
            p.end()
            return

        angle_step = 360.0 / n
        outer = QRectF(
            self._center.x() - self.radius,
            self._center.y() - self.radius,
            self.radius * 2,
            self.radius * 2,
        )

        for i in range(n):
            start_compass = i * angle_step
            qt_start = 90.0 - start_compass
            span = -angle_step  # 顺时针

            if i == self._hover_index:
                p.setBrush(QBrush(QColor(90, 170, 255, 160)))
                p.setPen(QPen(QColor(255, 255, 255, 220), 3))
            else:
                p.setBrush(QBrush(QColor(20, 20, 20, 150)))
                p.setPen(QPen(QColor(255, 255, 255, 90), 2))

            p.drawPie(outer, int(qt_start * 16), int(span * 16))

            # 在扇区中间放缩略图
            mid = math.radians(start_compass + angle_step / 2)
            dist = (self.radius + self.inner_radius) / 2
            cx = self._center.x() + dist * math.sin(mid)
            cy = self._center.y() - dist * math.cos(mid)
            pm = self._pixmaps[i]
            if pm is not None and not pm.isNull():
                box = int((self.radius - self.inner_radius) * 0.72)
                scaled = pm.scaled(box, box, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                p.drawPixmap(
                    int(cx - scaled.width() / 2),
                    int(cy - scaled.height() / 2),
                    scaled,
                )

        # 中心死区
        p.setBrush(QBrush(QColor(15, 15, 15, 190)))
        p.setPen(QPen(QColor(255, 255, 255, 70), 2))
        p.drawEllipse(self._center, self.inner_radius, self.inner_radius)
        p.end()
