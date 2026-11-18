"""Recolor Nubetalo Sound's brand mark; keep its rounded silhouette and wave."""
from pathlib import Path
import os
import struct
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QImage, QPixmap, QPainterPath
from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsBlurEffect

app = QApplication.instance() or QApplication([])
root = Path(__file__).resolve().parent.parent
brand = QImage(str(root / 'assets/brand-base.png')).convertToFormat(QImage.Format.Format_ARGB32)
assert not brand.isNull()
for y in range(brand.height()):
    for x in range(brand.width()):
        pixel = brand.pixelColor(x, y)
        r, g, b, a = pixel.getRgb()
        if b >= 30 and b > r and b > g:
            pixel = QColor(min(255, int((r * .8 + 25) * b / 255)), b,
                           min(255, int((r * .4 + 115) * b / 255)), a)
        elif max(r, g, b) < 30:
            pixel = QColor(7, 11, 9, a)
        brand.setPixelColor(x, y, pixel)
rounded = QImage(brand.size(), QImage.Format.Format_ARGB32_Premultiplied)
rounded.fill(Qt.GlobalColor.transparent)
mask = QPainter(rounded)
mask.setRenderHint(QPainter.RenderHint.Antialiasing)
outline = QPainterPath()
outline.addRoundedRect(QRectF(0, 0, brand.width(), brand.height()), 56, 56)
mask.setClipPath(outline)
mask.drawImage(0, 0, brand)
mask.end()
brand = rounded


def render(size):
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    light = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    light.fill(Qt.GlobalColor.transparent)
    source = QPainter(light)
    source.setRenderHint(QPainter.RenderHint.Antialiasing)
    source.scale(size / 256, size / 256)
    source.setBrush(Qt.BrushStyle.NoBrush)
    source.setPen(QPen(QColor('#57ff93'), 8))
    source.drawRoundedRect(QRectF(20, 20, 216, 216), 48, 48)
    source.end()
    scene = QGraphicsScene()
    item = scene.addPixmap(QPixmap.fromImage(light))
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(size / 256 * 12)
    item.setGraphicsEffect(blur)
    painter = QPainter(image)
    scene.render(painter, QRectF(0, 0, size, size), QRectF(0, 0, size, size))
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawImage(QRectF(size * 17 / 256, size * 17 / 256, size * 222 / 256, size * 222 / 256), brand)
    painter.end()
    return image


render(512).save(str(root / 'assets/logo.png'))
sizes = [16, 24, 32, 48, 64, 128, 256]
pngs = []
for size in sizes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert render(size).save(buffer, 'PNG')
    pngs.append(bytes(data))
offset = 6 + 16 * len(sizes)
directory = bytearray(struct.pack('<HHH', 0, 1, len(sizes)))
for size, png in zip(sizes, pngs):
    directory.extend(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(png), offset))
    offset += len(png)
(root / 'assets/app.ico').write_bytes(directory + b''.join(pngs))
assert render(32).pixelColor(0, 0).alpha() == 0
print('Original Nubetalo wave, vivid green halo, rounded transparent icon')
