"""设置面板：绑定快捷键、上传/管理表情、调整显示参数。"""
import copy
import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QMovie
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QDialogButtonBox,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

import config as config_mod
from emote_manager import import_emote, ALLOWED_EXTS
from hotkey import KeyCaptureThread


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("表情 Overlay 设置")
        self._config = copy.deepcopy(config)
        self._capture_target = None
        self._capture_thread = None
        self._preview_movie = None

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

        # 表情管理
        emote_box = QGroupBox("表情（PNG / GIF / WebP）")
        emote_layout = QVBoxLayout(emote_box)
        self._emote_list = QListWidget()
        self._emote_list.setIconSize(QSize(32, 32))
        self._emote_list.currentItemChanged.connect(self._on_select_emote)
        emote_layout.addWidget(self._emote_list)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("添加表情")
        self._add_btn.clicked.connect(self._add_emotes)
        self._remove_btn = QPushButton("删除")
        self._remove_btn.clicked.connect(self._remove_emote)
        self._up_btn = QPushButton("上移")
        self._up_btn.clicked.connect(lambda: self._move_emote(-1))
        self._down_btn = QPushButton("下移")
        self._down_btn.clicked.connect(lambda: self._move_emote(1))
        self._rename_btn = QPushButton("重命名")
        self._rename_btn.clicked.connect(self._rename_emote)
        for b in (self._add_btn, self._remove_btn, self._up_btn, self._down_btn, self._rename_btn):
            btn_row.addWidget(b)
        emote_layout.addLayout(btn_row)

        self._preview = QLabel("（预览）")
        self._preview.setFixedSize(96, 96)
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setStyleSheet("border: 1px solid #888;")
        emote_layout.addWidget(self._preview, alignment=Qt.AlignCenter)
        root.addWidget(emote_box)

        # 显示参数
        display_box = QGroupBox("显示")
        display_form = QFormLayout(display_box)
        self._pos_combo = QComboBox()
        for p in config_mod.POSITIONS:
            self._pos_combo.addItem(p, p)
        self._size_spin = QSpinBox()
        self._size_spin.setRange(64, 512)
        self._size_spin.setSuffix(" px")
        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setRange(0.5, 10.0)
        self._duration_spin.setSingleStep(0.1)
        self._duration_spin.setSuffix(" 秒")
        self._fade_check = QCheckBox("淡入淡出")
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

        self._emote_list.clear()
        for emote in self._config.get("emotes", []):
            item = QListWidgetItem(emote.get("name", ""))
            item.setData(Qt.UserRole, emote)
            icon = self._make_icon(emote)
            if icon is not None:
                item.setIcon(icon)
            self._emote_list.addItem(item)

        d = self._config.get("display", {})
        idx = self._pos_combo.findData(d.get("position", "bottom-center"))
        if idx >= 0:
            self._pos_combo.setCurrentIndex(idx)
        self._size_spin.setValue(int(d.get("size", 220)))
        self._duration_spin.setValue(float(d.get("duration", 2.5)))
        self._fade_check.setChecked(bool(d.get("fade", True)))

    @staticmethod
    def _make_icon(emote):
        path = emote.get("file", "")
        if not path or not os.path.exists(path):
            return None
        ext = os.path.splitext(path)[1].lower()
        if ext == ".gif":
            movie = QMovie(path)
            if movie.isValid():
                movie.jumpToFrame(0)
                return movie.currentPixmap().scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QPixmap(path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)

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

    # ---- 表情管理 ----
    def _add_emotes(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择表情图片", "", "表情图片 (*.png *.gif *.webp)"
        )
        for p in paths:
            emote = import_emote(p)
            self._config.setdefault("emotes", []).append(emote)
            item = QListWidgetItem(emote.get("name", ""))
            item.setData(Qt.UserRole, emote)
            icon = self._make_icon(emote)
            if icon is not None:
                item.setIcon(icon)
            self._emote_list.addItem(item)

    def _remove_emote(self):
        row = self._emote_list.currentRow()
        if row < 0:
            return
        self._emote_list.takeItem(row)
        self._config["emotes"].pop(row)
        self._clear_preview()

    def _move_emote(self, delta):
        row = self._emote_list.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self._emote_list.count():
            return
        item = self._emote_list.takeItem(row)
        self._emote_list.insertItem(new_row, item)
        self._emote_list.setCurrentRow(new_row)
        emotes = self._config["emotes"]
        emotes.insert(new_row, emotes.pop(row))

    def _rename_emote(self):
        row = self._emote_list.currentRow()
        if row < 0:
            return
        item = self._emote_list.item(row)
        name, ok = QInputDialog.getText(self, "重命名", "表情名称：", text=item.text())
        if ok and name.strip():
            item.setText(name.strip())
            self._config["emotes"][row]["name"] = name.strip()

    def _on_select_emote(self, current, _previous):
        self._update_preview(current)

    def _update_preview(self, item):
        self._clear_preview()
        if item is None:
            self._preview.setText("（预览）")
            return
        emote = item.data(Qt.UserRole)
        path = emote.get("file", "")
        if not path or not os.path.exists(path):
            self._preview.setText("（文件缺失）")
            return
        if os.path.splitext(path)[1].lower() == ".gif":
            self._preview_movie = QMovie(path)
            self._preview_movie.setScaledSize(QSize(96, 96))
            self._preview.setMovie(self._preview_movie)
            self._preview_movie.start()
        else:
            pm = QPixmap(path).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._preview.setPixmap(pm)

    def _clear_preview(self):
        if self._preview_movie is not None:
            self._preview_movie.stop()
            self._preview_movie = None
        self._preview.clear()
        self._preview.setPixmap(QPixmap())

    # ---- 确认 ----
    def _on_accept(self):
        self._clear_preview()
        if self._capture_thread is not None and self._capture_thread.isRunning():
            self._capture_thread.requestInterruption()
        self.accept()

    def get_config(self):
        return self._config
