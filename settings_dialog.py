"""设置面板：绑定快捷键、按「滚轮分组」管理表情、调整显示参数。"""
import copy
import math
import os

from PySide6.QtCore import Qt, QSize, QRectF, QPointF, Signal
from PySide6.QtGui import QPixmap, QMovie, QPainter, QColor, QPen, QBrush, QGuiApplication, QPainterPath
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QDialogButtonBox,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QWidget,
    QTabWidget,
)

from config import WHEEL_STYLES, WHEEL_STYLE_LABELS, WHEEL_THEMES, WHEEL_THEME_LABELS
from emote_manager import import_emote
from hotkey import KeyCaptureThread
from wheel import angle_index, INNER_RATIO, theme_palette, annular_sector, shadow_shift


def _thumb(emote):
    """GIF 取第一帧做缩略图，PNG/WebP 直接加载；文件缺失返回 None。"""
    path = emote.get("file", "")
    if not path or not os.path.exists(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gif":
        movie = QMovie(path)
        if movie.isValid():
            movie.jumpToFrame(0)
            pm = movie.currentPixmap()
            movie.stop()
            return pm
    return QPixmap(path)


class WheelPreview(QWidget):
    """把当前分组的表情按滚轮位置画成可拖拽的圆形，拖动表情即可换位。

    显示样式跟随设置（radial / sts2）。
    """

    selectionChanged = Signal(int)
    reordered = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._slots = []        # 表情槽位（含空表情占位）
        self._pixmaps = []
        self._selected = -1
        self._radius = 96
        self._style = "radial"
        self._theme = "dark"
        self._shadow_alpha = 180
        self._drag_index = -1
        self._drag_pos = QPointF()
        self.setMinimumSize(240, 240)

    def set_style(self, style):
        self._style = style
        self.update()

    def set_theme(self, theme):
        self._theme = theme
        self.update()

    def set_shadow_alpha(self, alpha):
        self._shadow_alpha = alpha
        self.update()

    def set_emotes(self, emotes):
        self._slots = list(emotes)
        self._pixmaps = [_thumb(e) for e in self._slots]
        self._selected = -1
        self._drag_index = -1
        self.update()

    def set_selected(self, index):
        self._selected = index
        self.update()

    def selected_index(self):
        return self._selected

    def _index_at(self, pos):
        if not self._slots:
            return -1
        dx = pos.x() - self.width() / 2
        dy = pos.y() - self.height() / 2
        return angle_index(dx, dy, len(self._slots))

    def mousePressEvent(self, event):
        if not self._slots:
            return
        idx = self._index_at(event.position())
        if idx < 0:
            return
        self._selected = idx
        self.update()
        self.selectionChanged.emit(idx)
        # 只有真实表情才能拖动，空表情槽只用于放置
        if self._slots[idx].get("file"):
            self._drag_index = idx
            self._drag_pos = event.position()

    def mouseMoveEvent(self, event):
        if self._drag_index < 0:
            return
        self._drag_pos = event.position()
        self.update()

    def mouseReleaseEvent(self, event):
        if self._drag_index < 0:
            return
        src = self._drag_index
        dst = self._index_at(event.position())
        self._drag_index = -1
        if dst >= 0 and dst != src:
            # 直接交换两个槽位，其余表情位置保持不变
            self._slots[src], self._slots[dst] = self._slots[dst], self._slots[src]
            self._pixmaps[src], self._pixmaps[dst] = self._pixmaps[dst], self._pixmaps[src]
            self._selected = dst
            self.reordered.emit(list(self._slots))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self._slots:
            p.setPen(QColor(128, 128, 128, 160))
            p.drawText(self.rect(), Qt.AlignCenter, "该分组为空，点击下方「添加表情」")
            p.end()
            return

        pal = theme_palette(self._theme)
        center = QPointF(self.width() / 2, self.height() / 2)
        n = len(self._slots)
        angle_step = 360.0 / n
        outer_r = self._radius
        is_sts2 = self._style == "sts2"
        inner_r = outer_r * INNER_RATIO if is_sts2 else 0.0
        base_shift = outer_r * 0.05

        hover_idx = self._index_at(self._drag_pos) if self._drag_index >= 0 else -1
        corner_r = max(2.0, outer_r * 0.05)
        shadow_offset = max(3.0, outer_r * 0.035)

        for i in range(n):
            # 两种风格统一：扇环中心落在 i*angle_step，0 号在正上方
            start_compass = i * angle_step - angle_step / 2
            span = angle_step
            qt_start = 90.0 - start_compass
            outer = QRectF(center.x() - outer_r, center.y() - outer_r,
                           outer_r * 2, outer_r * 2)
            mid = math.radians(i * angle_step)

            is_empty = not self._slots[i].get("file")
            if i == self._drag_index:
                brush = QColor(0, 0, 0, 90) if self._theme == "dark" else QColor(0, 0, 0, 45)
                pen = QPen(pal["sector_border"], 2)
                draw_shadow = False
            elif i == hover_idx:
                brush = QColor(185, 192, 205, 150)
                pen = Qt.NoPen
                draw_shadow = True
            elif i == self._selected:
                brush = pal["highlight"]
                pen = Qt.NoPen
                draw_shadow = True
            elif is_empty:
                brush = QColor(0, 0, 0, 30) if self._theme == "dark" else QColor(0, 0, 0, 18)
                pen = QPen(pal["sector_border"], 1, Qt.DashLine)
                draw_shadow = False
            else:
                brush = pal["sector"]
                pen = Qt.NoPen
                draw_shadow = True

            if is_sts2:
                path = annular_sector(center, outer_r, inner_r, start_compass, span, corner_r)
                path.translate(base_shift * math.sin(mid), -base_shift * math.cos(mid))

            if draw_shadow:
                p.setBrush(QBrush(QColor(0, 0, 0, self._shadow_alpha)))
                p.setPen(Qt.NoPen)
                sx, sy = shadow_shift(shadow_offset)
                if is_sts2:
                    sh = QPainterPath(path)
                    sh.translate(sx, sy)
                    p.drawPath(sh)
                else:
                    p.drawPie(outer.translated(sx, sy),
                              int(qt_start * 16), int(-span * 16))

            p.setBrush(QBrush(brush))
            p.setPen(pen)
            if is_sts2:
                p.drawPath(path)
            else:
                p.drawPie(outer, int(qt_start * 16), int(-span * 16))

            if i == self._drag_index or is_empty:
                continue  # 被拖拽的表情画在鼠标处；空表情槽无缩略图

            mid = math.radians(i * angle_step)
            dist = (outer_r + inner_r) / 2 + base_shift if is_sts2 else outer_r * 0.62
            cx = center.x() + dist * math.sin(mid)
            cy = center.y() - dist * math.cos(mid)
            pm = self._pixmaps[i]
            if pm is not None and not pm.isNull():
                box = int(outer_r * 0.46)
                scaled = pm.scaled(box, box, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                p.drawPixmap(int(cx - scaled.width() / 2),
                             int(cy - scaled.height() / 2), scaled)

        # 拖拽中的表情跟随鼠标
        if self._drag_index >= 0:
            pm = self._pixmaps[self._drag_index]
            if pm is not None and not pm.isNull():
                box = int(outer_r * 0.6)
                scaled = pm.scaled(box, box, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                p.setOpacity(0.85)
                p.drawPixmap(int(self._drag_pos.x() - scaled.width() / 2),
                             int(self._drag_pos.y() - scaled.height() / 2), scaled)
                p.setOpacity(1.0)
        p.end()


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("表情 Overlay 设置")
        self._config = copy.deepcopy(config)
        self._config.setdefault("groups", [])
        self._capture_target = None
        self._capture_thread = None
        self._selected_index = -1

        self._build_ui()
        self._load_from_config()

    # ---- UI ----
    def _build_ui(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()

        # 快捷键
        hotkey_box = QGroupBox("快捷键")
        hotkey_form = QFormLayout(hotkey_box)
        self._open_key_btn = QPushButton()
        self._open_key_btn.setFixedWidth(140)
        self._open_key_btn.clicked.connect(lambda: self._start_capture("hotkey_open"))
        self._dismiss_key_btn = QPushButton()
        self._dismiss_key_btn.setFixedWidth(140)
        self._dismiss_key_btn.clicked.connect(lambda: self._start_capture("hotkey_dismiss"))
        hotkey_form.addRow("呼出滚轮", self._open_key_btn)
        hotkey_form.addRow("关闭 / 取消", self._dismiss_key_btn)
        tabs.addTab(hotkey_box, "快捷键")

        # 表情管理（分组 + 圆形预览）
        emote_box = QGroupBox("表情（PNG / GIF / WebP）")
        emote_layout = QVBoxLayout(emote_box)

        group_row = QHBoxLayout()
        group_row.addWidget(QLabel("分组"))
        self._group_combo = QComboBox()
        self._group_combo.currentIndexChanged.connect(self._on_group_changed)
        group_row.addWidget(self._group_combo, stretch=1)
        self._add_group_btn = QPushButton("添加分组")
        self._add_group_btn.clicked.connect(self._add_group)
        self._remove_group_btn = QPushButton("删除分组")
        self._remove_group_btn.clicked.connect(self._remove_group)
        self._rename_group_btn = QPushButton("重命名分组")
        self._rename_group_btn.clicked.connect(self._rename_group)
        for b in (self._add_group_btn, self._remove_group_btn, self._rename_group_btn):
            group_row.addWidget(b)
        emote_layout.addLayout(group_row)

        self._preview = WheelPreview()
        emote_layout.addWidget(self._preview, alignment=Qt.AlignCenter)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("添加表情")
        self._add_btn.clicked.connect(self._add_emotes)
        self._add_empty_btn = QPushButton("添加空表情")
        self._add_empty_btn.clicked.connect(self._add_empty_emote)
        self._remove_btn = QPushButton("删除")
        self._remove_btn.clicked.connect(self._remove_emote)
        self._rename_btn = QPushButton("重命名")
        self._rename_btn.clicked.connect(self._rename_emote)
        for b in (self._add_btn, self._add_empty_btn, self._remove_btn, self._rename_btn):
            btn_row.addWidget(b)
        emote_layout.addLayout(btn_row)

        self._preview.selectionChanged.connect(self._on_preview_select)
        self._preview.reordered.connect(self._on_reordered)
        tabs.addTab(emote_box, "表情")

        # 显示参数
        display_box = QGroupBox("显示")
        display_form = QFormLayout(display_box)
        self._monitor_combo = QComboBox()
        self._monitor_combo.currentIndexChanged.connect(self._on_monitor_changed)
        self._size_spin = QSpinBox()
        self._size_spin.setRange(16, 512)
        self._size_spin.setSuffix(" px")
        self._offset_spin = QSpinBox()
        self._offset_spin.setRange(0, 200)
        self._offset_spin.setSuffix(" px")
        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setRange(0.5, 10.0)
        self._duration_spin.setSingleStep(0.1)
        self._duration_spin.setSuffix(" 秒")
        self._fade_check = QCheckBox("淡入淡出")
        self._return_cursor_check = QCheckBox("选择后鼠标回到原处")
        display_form.addRow("显示器", self._monitor_combo)
        display_form.addRow("表情大小", self._size_spin)
        display_form.addRow("上方偏移", self._offset_spin)
        display_form.addRow("显示时长", self._duration_spin)
        display_form.addRow("", self._fade_check)
        display_form.addRow("", self._return_cursor_check)
        tabs.addTab(display_box, "显示")

        # 轮盘风格
        wheel_box = QGroupBox("轮盘")
        wheel_form = QFormLayout(wheel_box)
        self._style_combo = QComboBox()
        for s in WHEEL_STYLES:
            self._style_combo.addItem(WHEEL_STYLE_LABELS.get(s, s), s)
        self._style_combo.currentIndexChanged.connect(self._on_wheel_setting_changed)
        wheel_form.addRow("风格", self._style_combo)

        self._radius_spin = QSpinBox()
        self._radius_spin.setRange(80, 400)
        self._radius_spin.setSuffix(" px")
        wheel_form.addRow("半径", self._radius_spin)

        self._theme_combo = QComboBox()
        for t in WHEEL_THEMES:
            self._theme_combo.addItem(WHEEL_THEME_LABELS.get(t, t), t)
        self._theme_combo.currentIndexChanged.connect(self._on_wheel_setting_changed)
        wheel_form.addRow("主题", self._theme_combo)

        self._shadow_spin = QSpinBox()
        self._shadow_spin.setRange(0, 255)
        self._shadow_spin.valueChanged.connect(self._on_wheel_setting_changed)
        wheel_form.addRow("阴影深浅", self._shadow_spin)
        tabs.addTab(wheel_box, "轮盘")

        root.addWidget(tabs)

        # 确认 / 取消
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ---- 载入配置 ----
    def _load_from_config(self):
        self._open_key_btn.setText(self._config.get("hotkey_open", ""))
        self._dismiss_key_btn.setText(self._config.get("hotkey_dismiss", ""))

        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        for group in self._config.get("groups", []):
            self._group_combo.addItem(group.get("name", "未命名"))
        self._group_combo.blockSignals(False)

        d = self._config.get("display", {})
        self._monitor_combo.blockSignals(True)
        self._monitor_combo.clear()
        self._monitor_combo.addItem("全部显示器", -1)
        for i, s in enumerate(QGuiApplication.screens()):
            g = s.geometry()
            self._monitor_combo.addItem(f"显示器 {i + 1}（{g.width()}×{g.height()}）", i)
        idx = self._monitor_combo.findData(int(d.get("monitor", 0)))
        self._monitor_combo.setCurrentIndex(max(0, idx))
        self._monitor_combo.blockSignals(False)

        self._size_spin.setValue(int(d.get("size", 220)))
        self._offset_spin.setValue(int(d.get("offset_y", 12)))
        self._duration_spin.setValue(float(d.get("duration", 2.5)))
        self._fade_check.setChecked(bool(d.get("fade", True)))
        self._return_cursor_check.setChecked(bool(d.get("return_cursor", True)))

        w = self._config.get("wheel", {})
        idx = self._style_combo.findData(w.get("style", "radial"))
        self._style_combo.setCurrentIndex(max(0, idx))
        self._radius_spin.setValue(int(w.get("radius", 130)))
        idx = self._theme_combo.findData(w.get("theme", "dark"))
        self._theme_combo.setCurrentIndex(max(0, idx))
        self._shadow_spin.setValue(int(w.get("shadow_alpha", 180)))

        self._selected_index = -1
        self._reload_preview()

    def _on_monitor_changed(self, _index):
        self._config.setdefault("display", {})["monitor"] = self._monitor_combo.currentData()

    def _on_wheel_setting_changed(self):
        # 风格 / 主题 / 阴影变化时即时刷新预览
        if hasattr(self, "_preview"):
            self._preview.set_style(self._style_combo.currentData())
            self._preview.set_theme(self._theme_combo.currentData())
            self._preview.set_shadow_alpha(self._shadow_spin.value())

    # ---- 分组 ----
    def _current_group(self):
        idx = self._group_combo.currentIndex()
        groups = self._config.get("groups", [])
        if 0 <= idx < len(groups):
            return groups[idx]
        return None

    def _reload_preview(self):
        group = self._current_group()
        emotes = group.get("emotes", []) if group else []
        self._preview.set_style(self._style_combo.currentData())
        self._preview.set_theme(self._theme_combo.currentData())
        self._preview.set_shadow_alpha(self._shadow_spin.value())
        self._preview.set_emotes(emotes)
        self._preview.set_selected(self._selected_index)
        self._update_emote_buttons()

    def _on_group_changed(self, _index):
        self._selected_index = -1
        self._reload_preview()

    def _add_group(self):
        groups = self._config.setdefault("groups", [])
        groups.append({"name": f"分组 {len(groups) + 1}", "emotes": []})
        self._group_combo.blockSignals(True)
        self._group_combo.addItem(groups[-1]["name"])
        self._group_combo.setCurrentIndex(self._group_combo.count() - 1)
        self._group_combo.blockSignals(False)
        self._selected_index = -1
        self._reload_preview()

    def _remove_group(self):
        idx = self._group_combo.currentIndex()
        if idx < 0:
            return
        if len(self._config.get("groups", [])) <= 1:
            QMessageBox.information(self, "表情 Overlay", "至少保留一个分组。")
            return
        self._config["groups"].pop(idx)
        self._group_combo.blockSignals(True)
        self._group_combo.removeItem(idx)
        self._group_combo.blockSignals(False)
        self._selected_index = -1
        self._reload_preview()

    def _rename_group(self):
        idx = self._group_combo.currentIndex()
        if idx < 0:
            return
        name, ok = QInputDialog.getText(self, "重命名分组", "分组名称：",
                                        text=self._group_combo.itemText(idx))
        if ok and name.strip():
            self._config["groups"][idx]["name"] = name.strip()
            self._group_combo.setItemText(idx, name.strip())

    # ---- 表情 ----
    def _add_emotes(self):
        group = self._current_group()
        if group is None:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择表情图片", "", "表情图片 (*.png *.gif *.webp)"
        )
        if not paths:
            return
        for p in paths:
            group.setdefault("emotes", []).append(import_emote(p))
        self._reload_preview()

    def _remove_emote(self):
        group = self._current_group()
        if group is None or self._selected_index < 0:
            return
        emotes = group.get("emotes", [])
        if 0 <= self._selected_index < len(emotes):
            emotes.pop(self._selected_index)
        self._selected_index = -1
        self._reload_preview()

    def _rename_emote(self):
        group = self._current_group()
        if group is None or self._selected_index < 0:
            return
        emotes = group.get("emotes", [])
        if not (0 <= self._selected_index < len(emotes)):
            return
        name, ok = QInputDialog.getText(self, "重命名", "表情名称：",
                                        text=emotes[self._selected_index].get("name", ""))
        if ok and name.strip():
            emotes[self._selected_index]["name"] = name.strip()

    def _add_empty_emote(self):
        group = self._current_group()
        if group is None:
            return
        group.setdefault("emotes", []).append({"file": "", "name": ""})
        self._selected_index = len(group["emotes"]) - 1
        self._reload_preview()

    def _on_preview_select(self, index):
        self._selected_index = index
        self._update_emote_buttons()

    def _on_reordered(self, new_order):
        group = self._current_group()
        if group is not None:
            group["emotes"] = list(new_order)
        self._selected_index = self._preview.selected_index()
        self._update_emote_buttons()

    def _update_emote_buttons(self):
        group = self._current_group()
        emotes = group.get("emotes", []) if group else []
        selected = group is not None and 0 <= self._selected_index < len(emotes)
        self._remove_btn.setEnabled(selected)
        # 重命名仅对真实表情有效（空表情无名称）
        rename_ok = selected and bool(emotes[self._selected_index].get("file"))
        self._rename_btn.setEnabled(rename_ok)

    # ---- 快捷键绑定 ----
    def _start_capture(self, target):
        if self._capture_thread is not None and self._capture_thread.isRunning():
            return
        self._capture_target = target
        btn = self._open_key_btn if target == "hotkey_open" else self._dismiss_key_btn
        btn.setText("请按键...")
        self._capture_thread = KeyCaptureThread(self)
        self._capture_thread.keyCaptured.connect(self._on_key_captured)
        self._capture_thread.start()

    def _on_key_captured(self, key):
        if not key:
            self._load_from_config()
        elif self._capture_target:
            self._config[self._capture_target] = key
            btn = self._open_key_btn if self._capture_target == "hotkey_open" else self._dismiss_key_btn
            btn.setText(key)
        self._capture_target = None
        self._capture_thread = None

    # ---- 确认 ----
    def _sync_display(self):
        d = self._config.setdefault("display", {})
        d["monitor"] = self._monitor_combo.currentData()
        d["size"] = self._size_spin.value()
        d["offset_y"] = self._offset_spin.value()
        d["duration"] = self._duration_spin.value()
        d["fade"] = self._fade_check.isChecked()
        d["return_cursor"] = self._return_cursor_check.isChecked()

        wheel = self._config.setdefault("wheel", {})
        wheel["style"] = self._style_combo.currentData()
        wheel["radius"] = self._radius_spin.value()
        wheel["theme"] = self._theme_combo.currentData()
        wheel["shadow_alpha"] = self._shadow_spin.value()

    def _on_accept(self):
        if self._capture_thread is not None and self._capture_thread.isRunning():
            self._capture_thread.requestInterruption()
        self._sync_display()
        self.accept()

    def get_config(self):
        return self._config
