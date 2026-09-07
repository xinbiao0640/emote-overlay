"""离线冒烟测试：验证模块导入、图片加载、滚轮角度判定、表情弹出。用 offscreen 平台。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

import config as config_mod
from wheel import angle_index


def main():
    app = QApplication(sys.argv)

    # 1. 配置加载
    cfg = config_mod.load_config()
    assert "hotkey_open" in cfg

    # 2. 图片加载
    sample = os.path.join(ROOT, "emotes", "thumbs_up.png")
    pm = QPixmap(sample)
    assert not pm.isNull(), "示例 PNG 无法加载"
    print("PNG 加载 OK:", pm.width(), "x", pm.height())

    # 3. 滚轮角度判定（只看方向角度，不限制距离）
    n = 6
    inner = cfg["wheel"]["inner_radius"]
    assert angle_index(0, -100, n, inner) == 0      # 正上方
    assert angle_index(100, 0, n, inner) == 1       # 正右方
    assert angle_index(0, 100, n, inner) == 3       # 正下方
    assert angle_index(0, 0, n, inner) == -1        # 死区
    assert angle_index(0, -9999, n, inner) == 0     # 很远仍按方向选中
    print("滚轮角度判定 OK")

    # 4. overlay / emote 模块可导入并构造
    from overlay import Overlay
    from emote import EmoteDisplay
    overlay = Overlay(cfg)
    disp = EmoteDisplay(overlay)
    print("Overlay / EmoteDisplay 构造 OK")

    # 5. 表情弹出
    emotes = [{"name": f"e{i}", "file": sample} for i in range(6)]
    overlay.set_emotes(emotes)
    overlay.show_emote(emotes[0])
    app.processEvents()
    assert overlay._emote_display.isVisible(), "表情未显示"
    print("表情弹出 OK")

    # 6. 松开选中并关闭滚轮
    overlay.open_wheel()
    app.processEvents()
    assert overlay._wheel_visible(), "滚轮未打开"
    overlay._wheel.set_hover_index(0)
    assert overlay._wheel.current_emote() is emotes[0]
    overlay.release_wheel()
    app.processEvents()
    assert not overlay._wheel_visible(), "松开后滚轮未关闭"
    print("松开选中 OK")

    print("SMOKE_OK")


if __name__ == "__main__":
    main()
