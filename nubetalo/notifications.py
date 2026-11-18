"""Brief completion island which never steals focus from another application."""
import sys
from PySide6.QtCore import Qt, QTimer, QVariantAnimation, QEasingCurve, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QFontMetrics, QCursor, QPainterPath
from PySide6.QtWidgets import QWidget, QApplication
from .theme import assets_dir


def play_completion_sound():
    if sys.platform == 'win32':
        import winsound
        try:
            winsound.PlaySound(str(assets_dir() / 'complete.wav'),
                              winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except RuntimeError:
            pass  # A disabled/unavailable audio device must not interrupt the queue.
    else:
        QApplication.beep()


class CompletionIsland(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet('background: transparent;')
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.message = ''
        self.heading = ''
        self.progress = 0.0
        self.closing = False
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(220)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.set_progress)
        self.animation.finished.connect(self.animation_finished)
        self.hold = QTimer(self)
        self.hold.setSingleShot(True)
        self.hold.timeout.connect(self.dismiss)

    def set_progress(self, value):
        self.progress = float(value)
        self.update()

    def show_download(self, name, language='es', count=1):
        self.hold.stop()
        self.animation.stop()
        self.message = name
        self.heading = ('Download completed' if language == 'en' else 'Descarga terminada') if count == 1 else (
            f'{count} downloads completed' if language == 'en' else f'{count} descargas terminadas')
        self.setAccessibleName(self.heading + ': ' + name)
        self.setToolTip(name)
        screen = self.parentWidget().screen() if self.parentWidget() and self.parentWidget().isVisible() else QApplication.screenAt(QCursor.pos())
        screen = screen or QApplication.primaryScreen()
        area = screen.availableGeometry()
        font = QFont('IBM Plex Sans')
        # Match the 13px rendered lettering in Sound's existing Windows capture.
        font.setPixelSize(11)
        metrics = QFontMetrics(font, self)
        content_width = metrics.horizontalAdvance(self.heading) + 84
        self.setFixedSize(min(420, area.width() - 24, max(170, content_width)), 56)
        self.move(area.center().x() - self.width() // 2, area.top() + 14)
        self.closing = False
        self.animation.setStartValue(self.progress if self.isVisible() else 0.0)
        self.animation.setEndValue(1.0)
        self.show()
        self.animation.start()
        self.hold.start(5500)

    def dismiss(self, animate=True):
        self.hold.stop()
        self.animation.stop()
        if not animate:
            self.hide()
            self.progress = 0.0
            return
        self.closing = True
        self.animation.setStartValue(self.progress)
        self.animation.setEndValue(0.0)
        self.animation.start()

    def animation_finished(self):
        if self.closing:
            self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            self.dismiss()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = 36 + (self.width() - 56) * self.progress
        pill = QRectF((self.width() - width) / 2, 10, width, 36)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for thickness, alpha in [(14, 3), (10, 6), (6, 10)]:
            color = QColor('#57ff93')
            color.setAlpha(int(alpha * self.progress))
            painter.setPen(QPen(color, thickness))
            painter.drawRoundedRect(pill, 18, 18)
        painter.setBrush(QColor('#0a100d'))
        color = QColor('#57ff93')
        color.setAlpha(int(105 * self.progress))
        painter.setPen(QPen(color, 1))
        painter.drawRoundedRect(pill, 18, 18)
        painter.setClipRect(pill)
        painter.setOpacity(min(1.0, max(0.0, (self.progress - .45) / .55)))
        # Sound's notification uses its bare ring/wave, never a desktop tile.
        painter.save()
        painter.translate(pill.x() + 15, 19)
        painter.scale(18 / 24, 18 / 24)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor('#57ff93'), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(3.8, 3.8, 16.4, 16.4), 58 * 16, -296 * 16)
        wave = QPainterPath()
        wave.moveTo(7.4, 12.6)
        wave.cubicTo(8.9, 8.6, 10.5, 8.6, 12, 12.6)
        wave.cubicTo(13.5, 16.6, 15.1, 16.6, 16.6, 12.6)
        painter.setPen(QPen(QColor('#b1ffce'), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(wave)
        painter.restore()
        text = QRectF(pill.x() + 42, 10, max(1, pill.width() - 58), 36)
        font = QFont('IBM Plex Sans')
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor('#eaf5ef'))
        message = painter.fontMetrics().elidedText(self.heading,
                                                  Qt.TextElideMode.ElideMiddle, int(text.width()))
        painter.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, message)
