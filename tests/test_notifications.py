import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from nubetalo.controller import Controller
from nubetalo.ui import MainWindow
from nubetalo.notifications import CompletionIsland
from nubetalo.theme import apply_theme


def test_completion_island_replaces_message_closes_and_does_not_focus():
    from PySide6.QtTest import QTest
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    island = CompletionIsland()
    island.show_download('archivo.zip')
    assert island.isVisible()
    assert 'archivo.zip' in island.message
    assert island.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert island.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert island.height() <= 56
    assert island.width() <= 420
    assert island.width() < 280
    assert island.toolTip() == 'archivo.zip'
    island.show_download('otro.zip')
    assert 'otro.zip' in island.message
    island.dismiss(animate=False)
    assert not island.isVisible()
    island.show_download('automático.zip')
    QTest.qWait(250)
    island.hold.timeout.emit()
    QTest.qWait(250)
    assert not island.isVisible()


def test_completion_uses_sound_and_island_with_independent_preferences(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    c = Controller(tmp_path, local_only=True)
    w = MainWindow(c, start_timer=False)
    task = c.add_http('https://example.com/a', str(tmp_path), 'a.zip')
    task.status = 'completed'
    sounds = []
    monkeypatch.setattr('nubetalo.ui.play_completion_sound', lambda: sounds.append(True))
    monkeypatch.setattr(c, 'tick', lambda: [task])
    w.tick()
    assert w.island.isVisible() and sounds == [True]
    w.island.dismiss(animate=False)
    w.tick()
    assert not w.island.isVisible() and sounds == [True]
    c.settings.completion_sound = False
    task.completion_notified = False
    w.tick()
    assert w.island.isVisible() and sounds == [True]
    w.island.dismiss(animate=False)
    c.settings.completion_notice = False
    task.completion_notified = False
    w.tick()
    assert not w.island.isVisible() and sounds == [True]
    w.hide()
    c.close()
