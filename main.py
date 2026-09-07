"""程序入口：创建透明 overlay、注册全局热键、系统托盘。"""
import sys

from PySide6.QtCore import Qt, QSharedMemory
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QFont
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox

import config as config_mod
from overlay import Overlay
from hotkey import HotkeyManager
from settings_dialog import SettingsDialog


def make_tray_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor("#4f7cff")))
    p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, 56, 56)
    p.setPen(QColor("white"))
    font = QFont("Segoe UI Emoji", 34)
    p.setFont(font)
    p.drawText(pm.rect(), Qt.AlignCenter, "😀")
    p.end()
    return QIcon(pm)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("EmoteOverlay")

    # 单实例守卫：避免重复启动导致双 overlay / venv 锁占用
    guard = QSharedMemory("emote-overlay-single-instance")
    if not guard.create(1):
        QMessageBox.information(None, "表情 Overlay", "程序已在运行（请查看系统托盘图标）。")
        sys.exit(0)

    cfg = config_mod.load_config()

    overlay = Overlay(cfg)

    hotkeys = HotkeyManager()
    hotkeys.openTriggered.connect(overlay.toggle_wheel)
    hotkeys.dismissTriggered.connect(overlay.close_wheel)
    hotkeys.set_hotkeys(cfg.get("hotkey_open"), cfg.get("hotkey_dismiss"))

    def apply_config(new_cfg):
        config_mod.save_config(new_cfg)
        overlay.set_emotes(new_cfg.get("emotes", []))
        overlay.set_display_cfg(new_cfg.get("display", {}))
        overlay.set_wheel_cfg(new_cfg.get("wheel", {}))
        hotkeys.set_hotkeys(new_cfg.get("hotkey_open"), new_cfg.get("hotkey_dismiss"))

    def open_settings():
        dlg = SettingsDialog(cfg)
        if dlg.exec():
            new_cfg = dlg.get_config()
            cfg.clear()
            cfg.update(new_cfg)
            apply_config(cfg)

    tray = QSystemTrayIcon(make_tray_icon(), app)
    tray.setToolTip("表情 Overlay")
    menu = QMenu()
    menu.addAction("设置", open_settings)
    menu.addSeparator()
    menu.addAction("退出", app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: open_settings()
        if reason == QSystemTrayIcon.DoubleClick
        else None
    )
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
