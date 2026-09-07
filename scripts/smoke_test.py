"""离线冒烟测试：验证模块导入、图片加载、滚轮角度计算。用 offscreen 平台，无需真实显示。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

import config as config_mod
from wheel import EmoteWheel


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

    # 3. 滚轮角度计算
    emotes = [{"name": f"e{i}", "file": sample} for i in range(6)]
    wheel = EmoteWheel(None, emotes, cfg["wheel"])
    center = wheel._center
    # 正上方 -> 索引 0
    assert wheel._index_at(QPointF(center.x(), center.y() - 100)) == 0
    # 正右方 -> 索引 1（6 个扇区，每 60°，顺时针：上=0 右=1）
    assert wheel._index_at(QPointF(center.x() + 100, center.y())) == 1
    # 正下方 -> 索引 3
    assert wheel._index_at(QPointF(center.x(), center.y() + 100)) == 3
    # 中心死区 -> -1
    assert wheel._index_at(QPointF(center.x(), center.y())) == -1
    print("滚轮角度计算 OK")

    # 4. overlay / emote 模块可导入并构造
    from overlay import Overlay
    from emote import EmoteDisplay
    overlay = Overlay(cfg)
    disp = EmoteDisplay(overlay)
    print("Overlay / EmoteDisplay 构造 OK")

    print("SMOKE_OK")


if __name__ == "__main__":
    main()
