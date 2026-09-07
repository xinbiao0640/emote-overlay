"""径向表情滚轮：围绕圆心分布表情，高亮索引由 overlay 按鼠标方向角度驱动。"""
import math
import os

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QMovie, QPolygonF, QPainterPath
from PySide6.QtWidgets import QWidget

# sts2 扇环内半径比例：越小中心透明区域越小，扇环越接近三角形
INNER_RATIO = 0.28


def _thumbnail(emote):
    """GIF 取第一帧做缩略图，PNG/WebP 直接加载；空表情返回 None。"""
    path = emote.get("file", "")
    if not path:
        return None
    if os.path.splitext(path)[1].lower() == ".gif":
        movie = QMovie(path)
        if movie.isValid():
            movie.jumpToFrame(0)
            pm = movie.currentPixmap()
            movie.stop()
            return pm
    return QPixmap(path)


def theme_palette(theme):
    """返回轮盘主题配色，供滚轮与设置预览共用。"""
    if theme == "light":
        return {
            "sector": QColor(235, 235, 235, 190),
            "sector_border": QColor(120, 120, 120, 170),
            "highlight": QColor(244, 245, 249, 252),
            "shadow": QColor(0, 0, 0, 45),
            "center": QColor(250, 250, 250, 230),
            "center_border": QColor(120, 120, 120, 140),
            "pointer": QColor(35, 35, 35, 235),
            "pointer_border": QColor(255, 255, 255, 210),
        }
    return {
        "sector": QColor(52, 54, 60, 190),
        "sector_border": QColor(255, 255, 255, 90),
        "highlight": QColor(88, 94, 110, 250),
        "shadow": QColor(0, 0, 0, 80),
        "center": QColor(40, 42, 48, 210),
        "center_border": QColor(255, 255, 255, 70),
        "pointer": QColor(255, 255, 255, 230),
        "pointer_border": QColor(0, 0, 0, 120),
    }


def angle_index(dx, dy, n):
    """根据方向向量计算高亮的表情索引。

    只看方向角度、不限制距离，无中心死区：只要不是恰好在中心点，
    移动多远都能选中对应方向的表情。中心点返回 -1（无选中）。

    扇区中心落在 i*step，0 号扇区中心在正上方（12 点方向）。
    """
    if n == 0 or (dx == 0 and dy == 0):
        return -1
    theta = math.degrees(math.atan2(dx, -dy))
    if theta < 0:
        theta += 360.0
    step = 360.0 / n
    theta += step / 2
    return int(theta // step) % n


def annular_sector(center, outer_r, inner_r, start_compass, span, corner_r=0.0):
    """构造扇环路径：外弧 + 两条径向边 + 内弧，中心（内圈以内）留空透明。

    start_compass 为罗盘角（0°=12点，顺时针），span 为顺时针跨度（度）。
    corner_r>0 时在四个角各做一个与两侧边相切的圆角（真正的倒角，而非顶点画圆）。
    """
    if corner_r <= 0:
        start = math.radians(start_compass)
        p1 = QPointF(center.x() + outer_r * math.sin(start),
                     center.y() - outer_r * math.cos(start))
        outer_rect = QRectF(center.x() - outer_r, center.y() - outer_r,
                            outer_r * 2, outer_r * 2)
        inner_rect = QRectF(center.x() - inner_r, center.y() - inner_r,
                            inner_r * 2, inner_r * 2)
        qt_start = 90.0 - start_compass
        qt_end = 90.0 - (start_compass + span)
        path = QPainterPath()
        path.moveTo(p1)
        path.arcTo(outer_rect, qt_start, -span)   # 外弧（顺时针）
        path.arcTo(inner_rect, qt_end, span)      # 内弧（逆时针，回起点）
        path.closeSubpath()
        return path

    cr = corner_r
    a0 = math.radians(start_compass)
    a1 = math.radians(start_compass + span)
    span_rad = a1 - a0
    # 圆角半径沿弧换算成角度偏移；clamp 保证每条弧至少保留一半长度
    da_out = min(cr / outer_r, span_rad / 4.0)
    da_in = min(cr / inner_r, span_rad / 4.0)

    def pt(ang, rho):
        return QPointF(center.x() + rho * math.sin(ang),
                       center.y() - rho * math.cos(ang))

    def _arc(p_from, rect, sweep_deg):
        # Qt 弧角度 0°=3点钟、逆时针为正、y 向下，故用 (center.y - p.y) 求角
        start_deg = math.degrees(math.atan2(rect.center().y() - p_from.y(),
                                            p_from.x() - rect.center().x()))
        path.arcTo(rect, start_deg, sweep_deg)

    def _fillet(f, c, p_from, p_to):
        rect = QRectF(f.x() - c, f.y() - c, c * 2, c * 2)
        a_from = math.degrees(math.atan2(f.y() - p_from.y(), p_from.x() - f.x()))
        a_to = math.degrees(math.atan2(f.y() - p_to.y(), p_to.x() - f.x()))
        sweep = a_to - a_from
        while sweep > 180.0:
            sweep -= 360.0
        while sweep < -180.0:
            sweep += 360.0
        path.arcTo(rect, a_from, sweep)

    outer_rect = QRectF(center.x() - outer_r, center.y() - outer_r, outer_r * 2, outer_r * 2)
    inner_rect = QRectF(center.x() - inner_r, center.y() - inner_r, inner_r * 2, inner_r * 2)

    path = QPainterPath()
    path.moveTo(pt(a0 + da_out, outer_r))
    _arc(pt(a0 + da_out, outer_r), outer_rect, -math.degrees(span_rad - 2 * da_out))
    _fillet(pt(a1 - da_out, outer_r - cr), cr, pt(a1 - da_out, outer_r), pt(a1, outer_r - cr))
    path.lineTo(pt(a1, inner_r + cr))
    _fillet(pt(a1 - da_in, inner_r + cr), cr, pt(a1, inner_r + cr), pt(a1 - da_in, inner_r))
    _arc(pt(a1 - da_in, inner_r), inner_rect, math.degrees(span_rad - 2 * da_in))
    _fillet(pt(a0 + da_in, inner_r + cr), cr, pt(a0 + da_in, inner_r), pt(a0, inner_r + cr))
    path.lineTo(pt(a0, outer_r - cr))
    _fillet(pt(a0 + da_out, outer_r - cr), cr, pt(a0, outer_r - cr), pt(a0 + da_out, outer_r))
    path.closeSubpath()
    return path


class EmoteWheel(QWidget):
    def __init__(self, parent, emotes, wheel_cfg):
        super().__init__(parent)
        self.radius = int(wheel_cfg.get("radius", 130))
        self.style = wheel_cfg.get("style", "radial")
        self.theme = wheel_cfg.get("theme", "dark")
        self._hover_index = -1
        self._pointer = QPointF(0, 0)

        self.setAttribute(Qt.WA_TranslucentBackground)
        # 滚轮本身不接收鼠标事件，交给 overlay 统一处理（滚轮切换分组等）
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        padding = 24
        size = (self.radius + padding) * 2
        self.resize(size, size)
        self._center = QPointF(self.width() / 2, self.height() / 2)

        self.emotes = []
        self._pixmaps = []
        self.set_emotes(emotes)

    def set_emotes(self, emotes):
        self.emotes = list(emotes)
        self._pixmaps = [_thumbnail(e) for e in self.emotes]
        self._hover_index = -1
        self._pointer = QPointF(0, 0)
        self.update()

    def slot_count(self):
        """返回槽位数量，供 overlay 计算高亮角度。"""
        return len(self.emotes)

    def set_hover_index(self, idx):
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()

    def set_pointer(self, dx, dy):
        """STS2 风格：设置中心圆内指针的偏移（相对圆心，已限制在中心圆内）。"""
        p = QPointF(dx, dy)
        if p != self._pointer:
            self._pointer = p
            self.update()

    def current_emote(self):
        """返回当前高亮的表情，未高亮或空表情返回 None。"""
        if 0 <= self._hover_index < len(self.emotes):
            emote = self.emotes[self._hover_index]
            if emote.get("file"):
                return emote
        return None

    def hover_index(self):
        """当前高亮槽位索引；-1 表示鼠标停在中心（无方向）。"""
        return self._hover_index

    def paintEvent(self, event):
        if self.style == "sts2":
            self._paint_sts2(event)
        else:
            self._paint_radial(event)

    def _paint_radial(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(self.emotes)
        if n == 0:
            p.end()
            return

        pal = theme_palette(self.theme)
        angle_step = 360.0 / n
        outer = QRectF(
            self._center.x() - self.radius,
            self._center.y() - self.radius,
            self.radius * 2,
            self.radius * 2,
        )
        shadow_offset = max(3.0, self.radius * 0.035)

        for i in range(n):
            # 扇区中心落在 i*angle_step，0 号在正上方
            start_compass = i * angle_step - angle_step / 2
            qt_start = 90.0 - start_compass
            span = -angle_step  # 顺时针

            # 阴影：向下偏移的深色半透明扇形，替代描边增加层次
            p.setBrush(QBrush(pal["shadow"]))
            p.setPen(Qt.NoPen)
            p.drawPie(outer.translated(0, shadow_offset),
                      int(qt_start * 16), int(span * 16))

            if i == self._hover_index:
                p.setBrush(QBrush(pal["highlight"]))
            else:
                p.setBrush(QBrush(pal["sector"]))
            p.setPen(Qt.NoPen)
            p.drawPie(outer, int(qt_start * 16), int(span * 16))

            # 在扇区中间放缩略图
            mid = math.radians(i * angle_step)
            dist = self.radius * 0.6
            cx = self._center.x() + dist * math.sin(mid)
            cy = self._center.y() - dist * math.cos(mid)
            pm = self._pixmaps[i]
            if pm is not None and not pm.isNull():
                box = int(self.radius * 0.44)
                scaled = pm.scaled(box, box, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                p.drawPixmap(
                    int(cx - scaled.width() / 2),
                    int(cy - scaled.height() / 2),
                    scaled,
                )

        p.end()

    def _paint_sts2(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(self.emotes)
        if n == 0:
            p.end()
            return

        pal = theme_palette(self.theme)
        outer_r = self.radius
        inner_r = self.radius * INNER_RATIO   # 内圈半径：以内为透明中心区域
        angle_step = 360.0 / n
        base_shift = self.radius * 0.05   # 每个扇环沿径向平移，撕出平行缝隙
        extra = self.radius * 0.10        # 高亮扇环额外突起
        corner_r = max(2.0, self.radius * 0.05)   # 扇环四角圆角半径
        shadow_offset = max(3.0, self.radius * 0.035)

        for i in range(n):
            # gap=0：扇环紧贴，中心落在 i*angle_step（i=0 即正上方）
            start_compass = i * angle_step - angle_step / 2
            span = angle_step

            highlighted = i == self._hover_index
            d = base_shift + (extra if highlighted else 0.0)

            # 构造无间隔扇环后，沿扇环中心径向平移 d；
            # 相邻扇环平移方向不同，原共享径向边被撕成两条严格平行的缝
            path = annular_sector(self._center, outer_r, inner_r, start_compass, span, corner_r)
            mid = math.radians(i * angle_step)
            tx = d * math.sin(mid)
            ty = -d * math.cos(mid)
            path.translate(tx, ty)

            # 阴影：向下偏移的深色半透明副本，替代描边增加层次
            shadow = QPainterPath(path)
            shadow.translate(0, shadow_offset)
            p.setBrush(QBrush(pal["shadow"]))
            p.setPen(Qt.NoPen)
            p.drawPath(shadow)

            fill = pal["highlight"] if highlighted else pal["sector"]
            p.setBrush(QBrush(fill))
            p.setPen(Qt.NoPen)
            p.drawPath(path)

            # 缩略图放在扇环中间，跟着扇环一起平移；高亮时放大更突出
            box = int(self.radius * (0.34 if highlighted else 0.26))
            dist = (outer_r + inner_r) / 2 + d
            cx = self._center.x() + dist * math.sin(mid)
            cy = self._center.y() - dist * math.cos(mid)
            pm = self._pixmaps[i]
            if pm is not None and not pm.isNull():
                scaled = pm.scaled(box, box, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                p.drawPixmap(
                    int(cx - scaled.width() / 2),
                    int(cy - scaled.height() / 2),
                    scaled,
                )

        # 选择指针：箭头（中心区域透明，无背景圆）
        pdx = self._pointer.x()
        pdy = self._pointer.y()
        dist = math.hypot(pdx, pdy)
        if dist < 1e-3:
            ux, uy = 0.0, -1.0
        else:
            ux, uy = pdx / dist, pdy / dist
        vx, vy = -uy, ux
        px = self._center.x() + pdx
        py = self._center.y() + pdy
        tip = QPointF(px + ux * 13, py + uy * 13)
        base = QPointF(px - ux * 4, py - uy * 4)
        left = QPointF(base.x() + vx * 6, base.y() + vy * 6)
        right = QPointF(base.x() - vx * 6, base.y() - vy * 6)
        arrow = QPolygonF([tip, left, right])
        p.setBrush(QBrush(pal["pointer"]))
        p.setPen(QPen(pal["pointer_border"], 1))
        p.drawPolygon(arrow)
        p.end()
