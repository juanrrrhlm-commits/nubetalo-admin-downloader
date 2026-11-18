import hashlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import queue
import threading
import time
from email.utils import formatdate
import pytest
from nubetalo.domain import Task
from nubetalo.http import HttpWorker

DATA = bytes(range(256)) * 16384


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        etag = '"original"'
        ranges = True
        cut = False
        unknown = False
        head_status = 200
        bad_range = False
        requests_seen = []

        def log_message(self, *args):
            pass

        def do_HEAD(self):
            self.send_response(self.head_status)
            if self.head_status == 200:
                if not self.unknown:
                    self.send_header('Content-Length', str(len(DATA)))
                self.send_header('ETag', self.etag)
                self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()

        def do_GET(self):
            if self.path == '/416':
                self.send_response(416)
                self.end_headers()
                return
            if self.path == '/redirect':
                self.send_response(302)
                self.send_header('Location', 'file:///C:/Windows/win.ini')
                self.end_headers()
                return
            start, end = 0, len(DATA) - 1
            requested = self.headers.get('Range')
            self.requests_seen.append(requested)
            if requested and self.ranges:
                parts = requested.removeprefix('bytes=').split('-')
                start, end = int(parts[0]), int(parts[1]) if parts[1] else end
                self.send_response(206)
                self.send_header('Content-Range', f'bytes {start + int(self.bad_range)}-{end}/{len(DATA)}')
            else:
                self.send_response(200)
            if not self.unknown:
                self.send_header('Content-Length', str(end - start + 1))
            self.send_header('ETag', self.etag)
            self.end_headers()
            try:
                body = DATA[start:end + 1]
                if self.cut:
                    body = body[:65536]
                for i in range(0, len(body), 16384):
                    self.wfile.write(body[i:i + 16384])
                    self.wfile.flush()
                    time.sleep(.001)
            except (ConnectionError, OSError):
                pass

    srv = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{srv.server_port}/file.bin', Handler
    srv.shutdown()
    srv.server_close()


def run(task, connections=4, stop=None):
    events = queue.Queue()
    worker = HttpWorker(task, events, stop or threading.Event(), lambda: 0, connections)
    worker.run()
    output = []
    while not events.empty():
        output.append(events.get())
    return output


def test_exact_file_and_hash(server, tmp_path):
    url, handler = server
    task = Task(source=url, destination=str(tmp_path), name='test.bin', checksum=hashlib.sha256(DATA).hexdigest())
    events = run(task)
    assert events[-1]['status'] == 'completed', events[-1]
    assert (tmp_path / task.name).read_bytes() == DATA
    assert events[-1]['verified']
    assert any(handler.requests_seen)


def test_ignored_ranges_explains_server_constraint(server, tmp_path):
    url, handler = server
    handler.ranges = False
    task = Task(source=url, destination=str(tmp_path), name='limited.bin')
    events = run(task)
    assert events[-1]['status'] == 'completed'
    assert any(e.get('server_notice') == 'ranges_ignored' for e in events)
    assert (tmp_path / task.name).read_bytes() == DATA


def test_busy_server_notice_and_retry_delay(server, tmp_path):
    url, handler = server
    handler.head_status = 429
    task = Task(source=url, destination=str(tmp_path), name='busy.bin')
    events = run(task)
    assert events[-1]['status'] == 'waiting'
    assert events[-1]['server_notice'] == 'http_429'
    assert events[-1]['retry_after'] == 30


def test_interrupted_resume(server, tmp_path):
    url, handler = server
    task = Task(source=url, destination=str(tmp_path), name='resume.bin')
    handler.cut = True
    assert run(task, 1)[-1]['status'] == 'waiting'
    assert not (tmp_path / task.name).exists()
    handler.cut = False
    assert run(task, 1)[-1]['status'] == 'completed'
    assert (tmp_path / task.name).read_bytes() == DATA
    assert any(r and not r.startswith('bytes=0-') for r in handler.requests_seen)


def test_changed_resource_never_appended(server, tmp_path):
    url, handler = server
    task = Task(source=url, destination=str(tmp_path), name='changed.bin')
    handler.cut = True
    run(task, 1)
    handler.cut = False
    handler.etag = '"changed"'
    result = run(task, 1)[-1]
    assert result['status'] == 'restart_required'
    assert not (tmp_path / task.name).exists()


def test_server_ignores_resume_range(server, tmp_path):
    url, handler = server
    task = Task(source=url, destination=str(tmp_path), name='ignore.bin')
    handler.cut = True
    run(task, 1)
    handler.cut = False
    handler.ranges = False
    assert run(task, 1)[-1]['status'] == 'restart_required'
    assert not (tmp_path / task.name).exists()


def test_does_not_overwrite_existing(server, tmp_path):
    url, _ = server
    (tmp_path / 'existing.bin').write_bytes(b'keep me')
    task = Task(source=url, destination=str(tmp_path), name='existing.bin')
    assert run(task)[-1]['status'] == 'error'
    assert (tmp_path / task.name).read_bytes() == b'keep me'


def test_unsafe_redirect(server, tmp_path):
    url, _ = server
    task = Task(source=url.replace('/file.bin', '/redirect'), destination=str(tmp_path), name='no.bin')
    assert run(task, 1)[-1]['status'] == 'error'
    assert not (tmp_path / task.name).exists()


def test_parallel_range_ignoring_falls_back_to_single(server, tmp_path):
    url, handler = server
    handler.ranges = False
    task = Task(source=url, destination=str(tmp_path), name='fallback.bin')
    assert run(task, 4)[-1]['status'] == 'completed'
    assert (tmp_path / task.name).read_bytes() == DATA


def test_recovers_published_file_before_completion_saved(server, tmp_path, monkeypatch):
    url, _ = server
    task = Task(source=url, destination=str(tmp_path), name='published.bin')
    real_emit = HttpWorker.emit

    def crash_on_completed(self, **data):
        if data.get('status') == 'completed':
            raise SystemExit('simulated crash')
        real_emit(self, **data)
    monkeypatch.setattr(HttpWorker, 'emit', crash_on_completed)
    with pytest.raises(SystemExit):
        run(task, 1)
    monkeypatch.setattr(HttpWorker, 'emit', real_emit)
    assert run(task, 1)[-1]['status'] == 'completed'
    assert (tmp_path / task.name).read_bytes() == DATA


def test_retry_after_http_date():
    from nubetalo.http import retry_delay
    assert 118 <= retry_delay(formatdate(time.time() + 120, usegmt=True)) <= 121


def test_https_redirect_cannot_drop_transport_security(monkeypatch, tmp_path):
    import pycurl
    from nubetalo.http import TransferError
    calls = []
    class RedirectResponse:
        def __init__(self):
            self.options = {}
        def setopt(self, key, value):
            self.options[key] = value
        def perform(self):
            calls.append(self.options[pycurl.URL])
            callback = self.options[pycurl.HEADERFUNCTION]
            callback(b'HTTP/1.1 302 Found\r\n')
            callback(b'Location: http://example.com/file\r\n')
        def close(self):
            pass
    monkeypatch.setattr(pycurl, 'Curl', RedirectResponse)
    worker = HttpWorker(Task('https://example.com/file', str(tmp_path)), queue.Queue(), threading.Event(), lambda: 0)
    with pytest.raises(TransferError, match='HTTPS downgrade blocked'):
        worker.request(worker.task.source, method='HEAD')
    assert len(calls) == 1


@pytest.mark.parametrize('head_status', [200, 405])
def test_unknown_size_or_head_unsupported(server, tmp_path, head_status):
    url, handler = server
    handler.unknown, handler.head_status = True, head_status
    task = Task(source=url, destination=str(tmp_path), name='unknown.bin', checksum=hashlib.sha256(DATA).hexdigest())
    assert run(task)[-1]['status'] == 'completed'
    assert (tmp_path / task.name).read_bytes() == DATA


def test_bad_content_range_rejected(server, tmp_path):
    url, handler = server
    handler.bad_range = True
    task = Task(source=url, destination=str(tmp_path), name='bad.bin')
    assert run(task)[-1]['status'] == 'restart_required'
    assert not (tmp_path / task.name).exists()


def test_416_requires_intervention(server, tmp_path):
    url, _ = server
    task = Task(source=url.replace('/file.bin', '/416'), destination=str(tmp_path), name='416.bin')
    assert run(task, 1)[-1]['status'] == 'restart_required'
    assert not (tmp_path / task.name).exists()


def test_disk_full_never_completes(server, tmp_path, monkeypatch):
    from collections import namedtuple
    monkeypatch.setattr('nubetalo.http.shutil.disk_usage', lambda path: namedtuple('Usage', 'total used free')(100,100,0))
    url, _ = server
    task = Task(source=url, destination=str(tmp_path), name='disk.bin')
    assert run(task, 1)[-1]['status'] == 'error'
    assert not (tmp_path / task.name).exists()


def test_real_two_http_tasks_share_cap(server, tmp_path):
    from nubetalo.controller import Controller
    url, _ = server
    c = Controller(tmp_path / 'app', local_only=True)
    c.settings.download_limit = 500000
    c.settings.connections = 1
    a = c.add_http(url, str(tmp_path), 'a.bin')
    b = c.add_http(url, str(tmp_path), 'b.bin')
    started = time.monotonic()
    while time.monotonic() - started < 2:
        c.tick()
        time.sleep(.02)
    assert 100000 < a.done + b.done <= 1200000
    c.pause(a.id)
    c.pause(b.id)
    c.close()
