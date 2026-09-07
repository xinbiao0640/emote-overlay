"""设置面板：绑定快捷键、按「滚轮分组」管理表情、调整显示参数。"""
import copy
import math
import os

from PySide6.QtCore import Qt, QSize, QRectF, QPointF, Signal
from PySide6.QtGui import QPixmap, QMovie, QPainter, QColor, QPen, QBrush, QGuiApplication
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
)

import config as config_mod
from emote_manager import import_emote
from hotkey import KeyCaptureThread
from wheel import angle_index


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
    """把当前分组的表情按滚轮位置画成可拖拽的圆形，拖动表情即可换位。"""

    selectionChanged = Signal(int)
    reordered = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._emotes = []
        self._selected = -1
        self._pixmaps = []
        self._radius = 96
        self._drag_index = -1
        self._drag_pos = QPointF()
        self.setMinimumSize(240, 240)

    def set_emotes(self, emotes):
        self._emotes = list(emotes)
        self._pixmaps = [_thumb(e) for e in self._emotes]
        self._selected = -1
        self._drag_index = -1
        self.update()

    def set_selected(self, index):
        self._selected = index
        self.update()

    def selected_index(self):
        return self._selected

    def _index_at(self, pos):
        if not self._emotes:
            return -1
        dx = pos.x() - self.width() / 2
        dy = pos.y() - self.height() / 2
        return angle_index(dx, dy, len(self._emotes))

    def mousePressEvent(self, event):
        if not self._emotes:
            return
        idx = self._index_at(event.position())
        if idx < 0:
            return
        self.set_selected(idx)
        self.selectionChanged.emit(idx)
        self._drag_index = idx
        self._drag_pos = event.position()
        self.update()

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
            self._emotes.insert(dst, self._emotes.pop(src))
            self._pixmaps.insert(dst, self._pixmaps.pop(src))
            self._selected = dst
            self.reordered.emit(list(self._emotes))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(self._emotes)
        if n == 0:
            p.setPen(QColor(255, 255, 255, 140))
            p.drawText(self.rect(), Qt.AlignCenter, "该分组为空，点击下方「添加表情」")
            p.end()
            return

        center = QPointF(self.width() / 2, self.height() / 2)
        outer = QRectF(center.x() - self._radius, center.y() - self._radius,
                       self._radius * 2, self._radius * 2)
        angle_step = 360.0 / n

        hover_idx = self._index_at(self._drag_pos) if self._drag_index >= 0 else -1

        for i in range(n):
            start_compass = i * angle_step
            qt_start = 90.0 - start_compass
            span = -angle_step
            if i == self._drag_index:
                p.setBrush(QBrush(QColor(40, 40, 40, 90)))
                p.setPen(QPen(QColor(255, 255, 255, 60), 2))
            elif i == hover_idx:
                p.setBrush(QBrush(QColor(90, 170, 255, 120)))
                p.setPen(QPen(QColor(255, 255, 255, 180), 3))
            elif i == self._selected:
                p.setBrush(QBrush(QColor(90, 170, 255, 160)))
                p.setPen(QPen(QColor(255, 255, 255, 220), 3))
            else:
                p.setBrush(QBrush(QColor(40, 40, 40, 150)))
                p.setPen(QPen(QColor(255, 255, 255, 90), 2))
            p.drawPie(outer, int(qt_start * 16), int(span * 16))

            if i == self._drag_index:
                continue  # 被拖拽的表情画在鼠标处

            mid = math.radians(start_compass + angle_step / 2)
            dist = self._radius * 0.62
            cx = center.x() + dist * math.sin(mid)
            cy = center.y() - dist * math.cos(mid)
            pm = self._pixmaps[i]
            if pm is not None and not pm.isNull():
                box = int(self._radius * 0.46)
                scaled = pm.scaled(box, box, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                p.drawPixmap(int(cx - scaled.width() / 2),
                             int(cy - scaled.height() / 2), scaled)

        p.setBrush(QBrush(QColor(15, 15, 15, 190)))
        p.setPen(QPen(QColor(255, 255, 255, 70), 2))
        p.drawEllipse(center, 16, 16)

        # 拖拽中的表情跟随鼠标
        if self._drag_index >= 0:
            pm = self._pixmaps[self._drag_index]
            if pm is not None and not pm.isNull():
                box = int(self._radius * 0.6)
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
        root.addWidget(hotkey_box)

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
        self._remove_btn = QPushButton("删除")
        self._remove_btn.clicked.connect(self._remove_emote)
        self._rename_btn = QPushButton("重命名")
        self._rename_btn.clicked.connect(self._rename_emote)
        self._up_btn = QPushButton("上移")
        self._up_btn.clicked.connect(lambda: self._move_emote(-1))
        self._down_btn = QPushButton("下移")
        self._down_btn.clicked.connect(lambda: self._move_emote(1))
        for b in (self._add_btn, self._remove_btn, self._rename_btn, self._up_btn, self._down_btn):
            btn_row.addWidget(b)
        emote_layout.addLayout(btn_row)

        self._preview.selectionChanged.connect(self._on_preview_select)
        self._preview.reordered.connect(self._on_reordered)
        root.addWidget(emote_box)

        # 显示参数
        display_box = QGroupBox("显示")
        display_form = QFormLayout(display_box)
        self._monitor_combo = QComboBox()
        self._monitor_combo.currentIndexChanged.connect(self._on_monitor_changed)
        self._pos_combo = QComboBox()
        for p in config_mod.POSITIONS:
            self._pos_combo.addItem(config_mod.POSITION_LABELS.get(p, p), p)
        self._size_spin = QSpinBox()
        self._size_spin.setRange(64, 512)
        self._size_spin.setSuffix(" px")
        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setRange(0.5, 10.0)
        self._duration_spin.setSingleStep(0.1)
        self._duration_spin.setSuffix(" 秒")
        self._fade_check = QCheckBox("淡入淡出")
        display_form.addRow("显示器", self._monitor_combo)
        display_form.addRow("弹出位置", self._pos_combo)
        display_form.addRow("表情大小", self._size_spin)
        display_form.addRow("显示时长", self._duration_spin)
        display_form.addRow("", self._fade_check)
        root.addWidget(display_box)

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
        for i, s in enumerate(QGuiApplication.screens()):
            g = s.geometry()
            self._monitor_combo.addItem(f"显示器 {i + 1}（{g.width()}×{g.height()}）", i)
        self._monitor_combo.setCurrentIndex(int(d.get("monitor", 0)))
        self._monitor_combo.blockSignals(False)

        idx = self._pos_combo.findData(d.get("position", "bottom-center"))
        if idx >= 0:
            self._pos_combo.setCurrentIndex(idx)
        self._size_spin.setValue(int(d.get("size", 220)))
        self._duration_spin.setValue(float(d.get("duration", 2.5)))
        self._fade_check.setChecked(bool(d.get("fade", True)))

        self._selected_index = -1
        self._reload_preview()

    def _on_monitor_changed(self, index):
        self._config.setdefault("display", {})["monitor"] = index

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

    def _move_emote(self, delta):
        group = self._current_group()
        if group is None or self._selected_index < 0:
            return
        emotes = group.get("emotes", [])
        if len(emotes) < 2 or not (0 <= self._selected_index < len(emotes)):
            return
        i = self._selected_index
        j = (i + delta) % len(emotes)
        emotes.insert(j, emotes.pop(i))
        self._selected_index = j
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
        has = self._current_group() is not None
        selected = has and self._selected_index >= 0
        for b in (self._remove_btn, self._rename_btn, self._up_btn, self._down_btn):
            b.setEnabled(selected)

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
    def _on_accept(self):
        if self._capture_thread is not None and self._capture_thread.isRunning():
            self._capture_thread.requestInterruption()
        self.accept()

    def get_config(self):
        return self._config
