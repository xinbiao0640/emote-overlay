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

    # 3. 滚轮角度判定（只看方向角度，不限制距离，无中心死区）
    n = 6
    assert angle_index(0, -100, n) == 0      # 正上方
    assert angle_index(100, 0, n) == 2       # 正右方（落在扇区 1/2 分界，顺时针归入扇区 2）
    assert angle_index(0, 100, n) == 3       # 正下方
    assert angle_index(0, 0, n) == -1        # 恰好中心点
    assert angle_index(0, -9999, n) == 0     # 很远仍按方向选中
    assert angle_index(1, -1, n) == 1        # 极靠近中心也选中（无死区），右上 45° 归入扇区 1
    print("滚轮角度判定 OK")

    # 4. overlay / emote 模块可导入并构造
    from overlay import Overlay
    from emote import EmoteDisplay
    overlay = Overlay(cfg)
    disp = EmoteDisplay(overlay)
    print("Overlay / EmoteDisplay 构造 OK")

    # 5. 表情弹出（支持多个同时显示）
    groups = [{"name": "测试", "emotes": [{"name": f"e{i}", "file": sample} for i in range(6)]}]
    overlay.set_groups(groups)
    overlay.show_emote(groups[0]["emotes"][0])
    overlay.show_emote(groups[0]["emotes"][1])
    app.processEvents()
    assert overlay._emote_display.active_count() == 2, "表情未显示"
    print("表情弹出 OK（多表情同时显示）")

    # 6. 松开选中并关闭滚轮
    overlay.open_wheel()
    app.processEvents()
    assert overlay._wheel_visible(), "滚轮未打开"
    overlay._wheel.set_hover_index(0)
    assert overlay._wheel.current_emote() is groups[0]["emotes"][0]
    overlay.release_wheel()
    app.processEvents()
    assert not overlay._wheel_visible(), "松开后滚轮未关闭"
    print("松开选中 OK")

    # 7. 分组切换（滚轮事件切换表情组）
    groups.append({"name": "第二组", "emotes": [{"name": f"g{i}", "file": sample} for i in range(3)]})
    overlay.set_groups(groups)
    overlay.open_wheel()
    app.processEvents()
    assert overlay._group_index == 0
    assert overlay._wheel.current_emote() is None  # 未高亮
    overlay._switch_group(1)
    assert overlay._group_index == 1
    assert len(overlay._wheel.emotes) == 3
    overlay.release_wheel()
    print("分组切换 OK")

    print("SMOKE_OK")


if __name__ == "__main__":
    main()
