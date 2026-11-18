"""HTTP transfers with validated ranges and durable per-segment checkpoints."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from urllib.parse import urljoin
import pycurl
from .domain import Task, safe_path, validate_url


class TransferError(Exception):
    def __init__(self, message, status='error', retry_after=0, server_notice=''):
        super().__init__(message)
        self.status, self.retry_after = status, retry_after
        self.server_notice = server_notice


def retry_delay(value):
    if value.isdigit():
        return int(value)
    try:
        return max(0, int((parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (ValueError, TypeError, OverflowError):
        return 60


class HostGate:
    """One shared connection budget for every task targeting the same server."""
    condition = threading.Condition()
    counts = {}

    @classmethod
    def acquire(cls, host, limit, cancelled):
        with cls.condition:
            while cls.counts.get(host, 0) >= limit:
                if cancelled():
                    raise TransferError('Pausada / Paused', 'paused')
                cls.condition.wait(.1)
            cls.counts[host] = cls.counts.get(host, 0) + 1

    @classmethod
    def release(cls, host):
        with cls.condition:
            cls.counts[host] -= 1
            cls.condition.notify_all()


class HttpWorker:
    def __init__(self, task: Task, events, stop: threading.Event, rate_limit, connections=4, streams=None):
        self.task, self.events, self.stop, self.rate_limit = task, events, stop, rate_limit
        self.connections = connections
        self.streams = max(1, min(connections, streams if streams is not None else connections))
        self.lock = threading.Lock()
        self.throttle = threading.Lock()
        self.next_byte_time = time.monotonic()
        self.last_emit = 0
        self.started = time.monotonic()
        self.initial_done = 0
        self.meta = {}
        self.abort = threading.Event()

    def cancelled(self):
        return self.stop.is_set() or self.abort.is_set()

    def emit(self, **data):
        self.events.put(dict(id=self.task.id, **data))

    def request(self, url, method='GET', headers=None, writer=None, validate=None):
        for _ in range(6):
            validate_url(url)
            from urllib.parse import urlsplit
            parsed = urlsplit(url)
            host = (parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
            HostGate.acquire(host, self.connections, self.cancelled)
            response = {}
            status = [0]
            checked = [False]
            failure = []
            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, url.encode('utf-8'))
            curl.setopt(pycurl.FOLLOWLOCATION, False)
            curl.setopt(pycurl.PROTOCOLS, pycurl.PROTO_HTTP | pycurl.PROTO_HTTPS)
            curl.setopt(pycurl.CONNECTTIMEOUT, 15)
            curl.setopt(pycurl.LOW_SPEED_LIMIT, 1)
            curl.setopt(pycurl.LOW_SPEED_TIME, 25)
            curl.setopt(pycurl.NOSIGNAL, 1)
            curl.setopt(pycurl.USERAGENT, 'NubetaloAdminDownloader/0.1')
            curl.setopt(pycurl.SSL_VERIFYPEER, 1)
            curl.setopt(pycurl.SSL_VERIFYHOST, 2)
            curl.setopt(pycurl.BUFFERSIZE, 16384)
            curl.setopt(pycurl.NOPROGRESS, False)
            curl.setopt(pycurl.XFERINFOFUNCTION, lambda *args: 1 if self.cancelled() else 0)
            if method == 'HEAD':
                curl.setopt(pycurl.NOBODY, True)
            if headers:
                curl.setopt(pycurl.HTTPHEADER, headers)

            def header(line):
                text = line.decode('iso-8859-1').strip()
                if text.startswith('HTTP/'):
                    status[0] = int(text.split()[1])
                    response.clear()
                elif ':' in text:
                    key, value = text.split(':', 1)
                    response[key.lower()] = value.strip()
                return len(line)

            def write(data):
                try:
                    if 300 <= status[0] < 400:
                        return len(data)
                    if not checked[0]:
                        if validate:
                            validate(status[0], response)
                        checked[0] = True
                    if writer:
                        writer(data)
                    return len(data)
                except Exception as exc:
                    failure.append(exc)
                    return 0

            curl.setopt(pycurl.HEADERFUNCTION, header)
            curl.setopt(pycurl.WRITEFUNCTION, write)
            try:
                curl.perform()
                if failure:
                    raise failure[0]
                if 300 <= status[0] < 400:
                    location = response.get('location')
                    if not location:
                        raise TransferError('Redirección sin destino / Missing redirect target')
                    url = urljoin(url, location)
                    validate_url(url)
                    if parsed.scheme == 'https' and urlsplit(url).scheme != 'https':
                        raise TransferError('Redirección HTTPS a HTTP bloqueada / HTTPS downgrade blocked')
                    continue
                if validate and not checked[0]:
                    validate(status[0], response)
                if method == 'HEAD':
                    self.emit(server_origin=parsed.scheme + '://' + parsed.netloc)
                return status[0], response
            except pycurl.error as exc:
                if failure:
                    raise failure[0]
                if self.cancelled():
                    raise TransferError('Pausada / Paused', 'paused') from exc
                if exc.args[0] in (pycurl.E_SSL_CACERT, pycurl.E_PEER_FAILED_VERIFICATION):
                    raise TransferError('Certificado HTTPS no válido / Invalid HTTPS certificate') from exc
                raise TransferError('Conexión interrumpida; se reintentará / Connection interrupted', 'waiting') from exc
            finally:
                curl.close()
                HostGate.release(host)
        raise TransferError('Demasiadas redirecciones / Too many redirects')

    def checkpoint(self):
        temporary = self.parts / 'state.new'
        with open(temporary, 'w', encoding='utf-8') as f:
            json.dump(self.meta, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, self.parts / 'state.json')

    def pace(self, count):
        with self.throttle:
            limit = self.rate_limit()
            now = time.monotonic()
            if limit > 0:
                self.next_byte_time = max(now, self.next_byte_time) + count / limit
                while not self.cancelled() and time.monotonic() < self.next_byte_time:
                    self.stop.wait(min(.1, self.next_byte_time - time.monotonic()))
            else:
                self.next_byte_time = now

    def progress(self, force=False):
        now = time.monotonic()
        if force or now - self.last_emit > .3:
            self.last_emit = now
            done = sum(s['done'] for s in self.meta['segments'])
            self.emit(status='downloading', done=done, total=self.meta['total'],
                      speed=int((done - self.initial_done) / max(.1, now - self.started)),
                      etag=self.meta['etag'], modified=self.meta['modified'])

    def segment(self, index):
        segment = self.meta['segments'][index]
        start, end, done = segment['start'], segment['end'], segment['done']
        if end >= 0 and done == end - start + 1:
            return
        partial = safe_path(self.parts, f'{index}.part')
        ranged = len(self.meta['segments']) > 1 or done > 0
        headers = []
        if ranged:
            if not self.meta['validator']:
                raise TransferError('El servidor no permite reanudación segura / Cannot resume safely', 'restart_required')
            headers = [f'Range: bytes={start + done}-{end if end >= 0 else ""}',
                       'If-Range: ' + self.meta['validator']]

        def validate(status, response):
            if status in (429, 503):
                retry = response.get('retry-after', '30')
                raise TransferError('Servidor ocupado / Server busy', 'waiting', retry_delay(retry), f'http_{status}')
            if status == 416:
                raise TransferError('Rango rechazado; revisar archivo / Range rejected', 'restart_required')
            if ranged:
                match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.get('content-range', ''))
                if status == 200 and self.initial_done == 0 and len(self.meta['segments']) > 1:
                    raise TransferError('El servidor ignora los rangos / Server ignores ranges', 'single_fallback')
                if status != 206 or not match or tuple(map(int, match.groups())) != (start + done, end, self.meta['total']):
                    raise TransferError('El origen cambió o no admite rangos / Unsafe range response', 'restart_required')
            elif status != 200:
                raise TransferError(f'HTTP {status}: revisar enlace / Check link')
            if self.meta['etag'] and response.get('etag') != self.meta['etag']:
                raise TransferError('El archivo remoto cambió / Remote file changed', 'restart_required')
            if not self.meta['etag'] and self.meta['modified'] and response.get('last-modified') != self.meta['modified']:
                raise TransferError('El archivo remoto cambió / Remote file changed', 'restart_required')
            length = response.get('content-length')
            if length and end >= 0 and int(length) != end - start - done + 1:
                raise TransferError('Tamaño de respuesta incoherente / Response size mismatch', 'restart_required')

        with open(partial, 'r+b' if partial.exists() else 'w+b') as file:
            file.truncate(done)
            file.seek(done)
            checkpoint_time = [time.monotonic()]

            def persist():
                file.flush()
                os.fsync(file.fileno())
                with self.lock:
                    segment['done'] = file.tell()
                    self.checkpoint()
                    self.progress()

            def write(data):
                if self.cancelled():
                    raise TransferError('Pausada / Paused', 'paused')
                self.pace(len(data))
                if end >= 0 and file.tell() + len(data) > end - start + 1:
                    raise TransferError('Respuesta excede el tamaño / Response exceeds expected size')
                if shutil.disk_usage(self.parts).free < len(data) + 1024 * 1024:
                    raise TransferError('No hay espacio en disco / Disk full')
                file.write(data)
                if time.monotonic() - checkpoint_time[0] >= .5:
                    persist()
                    checkpoint_time[0] = time.monotonic()
            try:
                self.request(self.task.source, headers=headers, writer=write, validate=validate)
            finally:
                persist()

    def run(self):
        try:
            root = Path(self.task.destination)
            root.mkdir(parents=True, exist_ok=True)
            target = safe_path(root, self.task.name)
            self.parts = safe_path(root, '.nubetalo-' + self.task.id)
            if target.exists():
                state_path = safe_path(self.parts, 'state.json')
                if state_path.exists():
                    previous = json.loads(state_path.read_text(encoding='utf-8'))
                    expected = previous.get('final_sha256')
                    if expected and previous.get('final_size') == target.stat().st_size:
                        with open(target, 'rb') as f:
                            actual = hashlib.file_digest(f, 'sha256').hexdigest()
                        if actual == expected and (not self.task.checksum or actual == self.task.checksum.lower()):
                            self.emit(status='completed', done=target.stat().st_size, total=target.stat().st_size,
                                      speed=0, verified=bool(self.task.checksum), error='')
                            return
                raise TransferError('El archivo ya existe; cambia el nombre / File already exists')
            self.parts.mkdir(exist_ok=True)
            state = self.parts / 'state.json'
            status, headers = self.request(self.task.source, method='HEAD')
            if status in (429, 503):
                retry = headers.get('retry-after', '30')
                raise TransferError('Servidor ocupado / Server busy', 'waiting', retry_delay(retry), f'http_{status}')
            if status >= 400 and status not in (405, 501):
                raise TransferError(f'HTTP {status}: revisar enlace / Check link')
            total = int(headers.get('content-length', 0)) if status == 200 else 0
            etag = headers.get('etag', '')
            if etag.startswith('W/'):
                etag = ''
            modified = headers.get('last-modified', '')
            validator = etag or modified
            # Only explicit protocol evidence, never infer throttling from low speed.
            self.emit(error='', server_notice='no_ranges' if headers.get('accept-ranges', '').lower() == 'none' else '')
            if state.exists():
                safe_path(self.parts, 'state.json')
                self.meta = json.loads(state.read_text(encoding='utf-8'))
                if self.meta['etag'] != etag or self.meta['modified'] != modified or self.meta['total'] != total:
                    raise TransferError('El archivo remoto cambió / Remote file changed', 'restart_required')
                for i, seg in enumerate(self.meta['segments']):
                    p = safe_path(self.parts, f'{i}.part')
                    seg['done'] = min(seg['done'], p.stat().st_size if p.exists() else 0)
            else:
                count = min(self.streams, 4) if total >= 2 * 1024 * 1024 and validator and headers.get('accept-ranges') == 'bytes' else 1
                segments = [dict(start=total * i // count, end=total * (i + 1) // count - 1 if total else -1, done=0) for i in range(count)]
                self.meta = dict(total=total, etag=etag, modified=modified, validator=validator, segments=segments)
                self.checkpoint()
            self.initial_done = sum(s['done'] for s in self.meta['segments'])
            self.emit(http_streams=min(self.streams, len(self.meta['segments'])))
            self.progress(True)
            with ThreadPoolExecutor(max_workers=min(self.streams, len(self.meta['segments']))) as pool:
                futures = [pool.submit(self.segment, i) for i in range(len(self.meta['segments']))]
                failure = None
                for future in futures:
                    try:
                        future.result()
                    except Exception as exc:
                        if not failure or isinstance(failure, TransferError) and failure.status == 'paused':
                            failure = exc
                        self.abort.set()
                if failure:
                    if isinstance(failure, TransferError) and failure.status == 'single_fallback' and not self.initial_done:
                        self.emit(server_notice='ranges_ignored', http_streams=1)
                        self.abort.clear()
                        self.meta['segments'] = [dict(start=0, end=total - 1 if total else -1, done=0)]
                        self.checkpoint()
                        self.segment(0)
                    else:
                        raise failure
            if self.stop.is_set():
                raise TransferError('Pausada / Paused', 'paused')
            self.emit(status='checking', speed=0)
            combined = safe_path(self.parts, 'complete.tmp')
            digest = hashlib.sha256()
            written = 0
            with open(combined, 'wb') as output:
                for i in range(len(self.meta['segments'])):
                    with open(safe_path(self.parts, f'{i}.part'), 'rb') as source:
                        while chunk := source.read(1024 * 1024):
                            output.write(chunk)
                            digest.update(chunk)
                            written += len(chunk)
                output.flush()
                os.fsync(output.fileno())
            if total and written != total:
                raise TransferError('Archivo incompleto / Incomplete file', 'waiting')
            if self.task.checksum and digest.hexdigest().lower() != self.task.checksum.lower():
                raise TransferError('La huella SHA-256 no coincide / SHA-256 mismatch', 'restart_required')
            safe_path(root, self.task.name)
            self.meta.update(final_sha256=digest.hexdigest(), final_size=written)
            self.checkpoint()
            # Windows rename is atomic, supports non-NTFS volumes and refuses overwrite.
            if os.name == 'nt':
                os.rename(combined, target)
            else:
                os.link(combined, target)
            # Publish completion before cleanup so a crash can reconcile using its marker.
            self.emit(status='completed', done=written, total=written, speed=0, verified=bool(self.task.checksum), error='')
            # Only known files created by this task, never a recursive directory delete.
            try:
                for i in range(len(self.meta['segments'])):
                    safe_path(self.parts, f'{i}.part').unlink(missing_ok=True)
                for name in ('state.new', 'complete.tmp'):
                    safe_path(self.parts, name).unlink(missing_ok=True)
                # Keep the tiny publication receipt until the controller commits completed.
            except OSError:
                pass  # A valid final file must not be reported as failed due to temp cleanup.
        except TransferError as exc:
            self.emit(status=exc.status, error=str(exc), speed=0, retry_after=exc.retry_after, server_notice=exc.server_notice)
        except (OSError, ValueError, KeyError) as exc:
            self.emit(status='error', error='Error de archivo o configuración / File or configuration error', speed=0)
