"""生成几个示例表情 PNG（emoji 渲染），方便首次运行即可测试。"""
import os
import sys

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter, QFont, QColor
from PySide6.QtWidgets import QApplication

SAMPLES = [
    ("thumbs_up", "👍"),
    ("joy", "😂"),
    ("heart", "❤️"),
    ("surprised", "😮"),
    ("fire", "🔥"),
    ("cry", "😭"),
]


def main():
    app = QApplication(sys.argv)
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "emotes")
    os.makedirs(out_dir, exist_ok=True)

    size = 256
    font = QFont("Segoe UI Emoji")
    font.setPixelSize(int(size * 0.8))

    for name, glyph in SAMPLES:
        img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(font)
        p.setPen(QColor("white"))
        p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, glyph)
        p.end()
        path = os.path.join(out_dir, f"{name}.png")
        img.save(path)
        print("生成:", path)


if __name__ == "__main__":
    main()
