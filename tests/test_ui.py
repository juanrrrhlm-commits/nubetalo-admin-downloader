import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PySide6.QtWidgets import QApplication, QPushButton
from nubetalo.controller import Controller
from nubetalo.ui import MainWindow
from nubetalo.domain import DONATE_URL


def test_window_controls_translation_and_task(tmp_path):
    app = QApplication.instance() or QApplication([])
    c = Controller(tmp_path, local_only=True)
    w = MainWindow(c, start_timer=False)
    task = c.add_http('https://example.com/test.bin', str(tmp_path / 'downloads'), 'test.bin')
    c.pause(task.id)
    w.refresh()
    assert w.table.topLevelItemCount() == 1
    assert w.table.topLevelItem(0).text(0) == 'test.bin'
    assert any(b.text() == 'Añadir descarga' for b in w.findChildren(QPushButton))
    w.change_language('en')
    assert any(b.text() == 'Add download' for b in w.findChildren(QPushButton))
    assert parse_qs(urlparse(DONATE_URL).query)['item_name'] == ['Nubetalo Admin Downloader']
    assert 'paypal.com' == urlparse(DONATE_URL).hostname.removeprefix('www.')
    w.hide()
    c.close()


def test_mbps_and_megabytes_conversion():
    from nubetalo.dialogs import RateInput
    app = QApplication.instance() or QApplication([])
    rate = RateInput(1000000, lambda s: s)
    rate.unit.setCurrentText('Mbps')
    assert rate.spin.value() == 8
    assert rate.bytes_per_second() == 1000000
    rate.spin.setValue(4)
    assert rate.bytes_per_second() == 500000


def test_main_priority_eta_and_server_tooltip(tmp_path):
    from PySide6.QtCore import Qt
    app = QApplication.instance() or QApplication([])
    c = Controller(tmp_path, local_only=True)
    w = MainWindow(c, start_timer=False)
    a = c.add_http('https://example.com/a', str(tmp_path / 'd'), 'a.bin')
    b = c.add_http('https://example.com/b', str(tmp_path / 'd'), 'b.bin')
    c.pause(a.id)
    c.pause(b.id)
    c.settings.download_limit = 1000000
    a.status, a.total, a.speed = 'downloading', 3600000, 1000
    a.server_notice = 'http_429'
    a.error = 'Error de archivo / File error'
    w.refresh()
    item = next(w.table.topLevelItem(i) for i in range(w.table.topLevelItemCount())
                if w.table.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) == a.id)
    assert item.text(5) == '1 hora'
    assert not item.icon(4).isNull()
    assert 'HTTP 429' in item.toolTip(4)
    assert 'Error de archivo' in item.toolTip(4)
    item.setSelected(True)
    w.policy_buttons['priority'].click()
    assert c.tasks[a.id].priority == 2
    assert c.tasks[b.id].priority == 1
    assert c.settings.bandwidth_mode == 'priority'
    w.policy_buttons['equal'].click()
    assert c.tasks[a.id].priority == 1
    w.policy_buttons['free'].click()
    assert c.settings.download_limit == 0
    w.hide()
    c.close()


def test_details_priority_requests_budget_and_respects_cancel(tmp_path, monkeypatch):
    from nubetalo.dialogs import DetailsDialog
    app = QApplication.instance() or QApplication([])
    c = Controller(tmp_path, local_only=True)
    w = MainWindow(c, start_timer=False)
    task = c.add_http('https://example.com/x', str(tmp_path), 'x.bin')
    c.pause(task.id)
    d = DetailsDialog(w, task)
    d.priority.setCurrentIndex(2)
    monkeypatch.setattr(w, 'request_bandwidth', lambda: None)
    d.confirm()
    assert task.priority == 1 and c.settings.download_limit == 0
    monkeypatch.setattr(w, 'request_bandwidth', lambda: 1000000)
    d.confirm()
    assert task.priority == 2 and c.settings.download_limit == 1000000
    assert c.settings.bandwidth_mode == 'priority'
    w.hide()
    c.close()
