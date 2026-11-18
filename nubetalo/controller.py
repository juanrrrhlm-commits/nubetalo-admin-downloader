from pathlib import Path
from queue import Queue, Empty
from urllib.parse import urlsplit, unquote
import shutil
import threading
import time
from .domain import Task, Settings, validate_url, safe_path, time_window
from .store import Store
from .http import HttpWorker
from .torrents import TorrentEngine


def allocate_limits(total: int, caps: list[int], weights: list[int] | None = None) -> list[int]:
    if not total:
        return list(caps)
    weights = weights or [1] * len(caps)
    if len(weights) != len(caps) or any(w <= 0 for w in weights):
        raise ValueError('Invalid bandwidth weights')
    remaining = list(range(len(caps)))
    output = [0] * len(caps)
    budget = total
    while remaining:
        weight_sum = sum(weights[i] for i in remaining)
        small = [i for i in remaining if caps[i] and caps[i] < budget * weights[i] / weight_sum]
        if not small:
            for i in remaining:
                output[i] = max(1, budget * weights[i] // weight_sum)
            # Allocate integer rounding without turning a zero cap into unlimited.
            remainder = budget - sum(output[i] for i in remaining)
            for i in remaining[:max(0, remainder)]:
                output[i] += 1
            break
        for i in small:
            output[i] = caps[i]
            budget -= caps[i]
            remaining.remove(i)
    return output


class Controller:
    def __init__(self, data_dir: Path, local_only=False):
        self.data_dir = data_dir
        self.store = Store(data_dir / 'state.db')
        self.settings = self.store.settings()
        self.tasks = {t.id: t for t in self.store.load_tasks()}
        self.engine = TorrentEngine(data_dir / 'torrents', local_only)
        self.workers, self.events, self.retry_at = {}, Queue(), {}
        self.rates, self.finished_seed = {}, set()
        self.last_tick = time.monotonic()
        self.last_saved = 0
        for task in self.tasks.values():
            task.speed = task.upload_speed = 0
            task.http_streams = 0
            if task.status not in ('completed', 'error', 'restart_required'):
                task.status = 'paused' if task.manual_pause else 'queued'
            if task.kind == 'torrent' and task.status != 'completed':
                try:
                    self.engine.add(task, self._schedule_allowed())
                except (RuntimeError, ValueError, OSError):
                    task.status, task.error = 'error', 'No se pudo recuperar el torrent / Cannot restore torrent'

    def add_http(self, url, folder, name='', checksum=''):
        validate_url(url)
        name = name or unquote(Path(urlsplit(url).path).name) or 'download.bin'
        target = safe_path(Path(folder), name)
        if target.exists() or any(Path(t.destination).absolute() / t.name == target for t in self.tasks.values()):
            raise ValueError('El destino ya está en uso / Destination already in use')
        if checksum and (len(checksum) != 64 or any(c not in '0123456789abcdefABCDEF' for c in checksum)):
            raise ValueError('Huella SHA-256 inválida / Invalid SHA-256')
        task = Task(source=url, destination=folder, name=name, checksum=checksum)
        self.tasks[task.id] = task
        self.store.save_task(task)
        return task

    def add_torrent(self, source, folder):
        Path(folder).mkdir(parents=True, exist_ok=True)
        safe_path(Path(folder), 'path-check')
        task = Task(source=source, destination=folder, kind='torrent')
        self.engine.add(task, self._schedule_allowed())
        files = self.engine.files(task.id)
        if files:
            try:
                self._check_torrent_conflicts(task, files)
            except ValueError:
                self.engine.remove(task.id)
                raise
        self.tasks[task.id] = task
        self.store.save_task(task)
        return task

    def _check_torrent_conflicts(self, task, files):
        targets = {safe_path(Path(task.destination), f['name']) for f in files if not f['pad']}
        if any(p.exists() for p in targets):
            raise ValueError('El torrent contiene archivos que ya existen / Torrent files already exist')
        for other in self.tasks.values():
            if other.id == task.id:
                continue
            if other.kind == 'http' and Path(other.destination) / other.name in targets:
                raise ValueError('Destino usado por otra descarga / Target used by another task')
            if other.kind == 'torrent' and other.id in self.engine.handles:
                if targets.intersection(safe_path(Path(other.destination), f['name']) for f in self.engine.files(other.id) if not f['pad']):
                    raise ValueError('Destino usado por otro torrent / Target used by another torrent')

    def select(self, task_id, indices, priorities=None):
        task = self.tasks[task_id]
        self._check_torrent_conflicts(task, self.engine.files(task_id))
        self.engine.select(task_id, indices, priorities)
        task.status, task.manual_pause = 'queued', False
        self.store.save_task(task)

    def pause(self, task_id):
        task = self.tasks[task_id]
        if task.status == 'completed':
            return
        task.manual_pause, task.status = True, 'paused'
        task.speed = task.upload_speed = 0
        if task_id in self.workers:
            self.workers[task_id][1].set()
        if task.kind == 'torrent':
            self.engine.pause(task_id)
        self.store.save_task(task)

    def resume(self, task_id):
        task = self.tasks[task_id]
        if task.status in ('completed', 'restart_required'):
            return
        task.manual_pause, task.status, task.error = False, 'queued', ''
        if task.kind == 'torrent' and task.selected is None and task.id in self.engine.handles and self._schedule_allowed():
            self.engine.resume(task.id)
        self.retry_at.pop(task_id, None)
        self.store.save_task(task)

    def restart(self, task_id):
        task = self.tasks[task_id]
        if task_id in self.workers:
            raise ValueError('Espera a que se pause / Wait until paused')
        if task.kind == 'http':
            parts = safe_path(Path(task.destination), '.nubetalo-' + task.id)
            if parts.exists():
                for path in parts.iterdir():
                    if not (path.name in ('state.json', 'state.new', 'complete.tmp') or path.name.removesuffix('.part').isdigit()):
                        raise ValueError('Carpeta temporal inesperada / Unexpected temporary folder')
                    safe_path(parts, path.name).unlink()
                parts.rmdir()
        task.done, task.etag, task.modified = 0, '', ''
        task.status = 'queued'
        self.resume(task_id)

    def replace_url(self, task_id, url):
        validate_url(url)
        task = self.tasks[task_id]
        if task.kind != 'http' or task_id in self.workers:
            raise ValueError('Pausa primero / Pause first')
        task.source = url
        self.resume(task_id)  # Worker compares existing checkpoint identity before appending.
        self.store.save_task(task)

    def remove(self, task_id):
        if task_id in self.workers:
            self.pause(task_id)
            raise ValueError('Pausando; vuelve a quitar al detenerse / Pausing; remove after stopping')
        task = self.tasks[task_id]
        if task.kind == 'torrent':
            self.engine.remove(task_id)
        self.tasks.pop(task_id)
        self.store.delete_task(task_id)

    def apply_settings(self, settings):
        self.settings = settings
        self.store.save_settings(settings)

    def set_bandwidth_policy(self, mode, task_ids=None, total=None):
        if mode not in ('equal', 'priority', 'free'):
            raise ValueError('Invalid bandwidth mode')
        task_ids = set(task_ids or [])
        if not task_ids.issubset(self.tasks) or mode == 'priority' and not task_ids:
            raise ValueError('Selecciona una descarga / Select a download')
        if total is not None and total <= 0:
            raise ValueError('Velocidad inválida / Invalid speed')
        for task in self.tasks.values():
            task.priority = 2 if mode == 'priority' and task.id in task_ids else 1
            self.store.save_task(task)
        self.settings.bandwidth_mode = mode
        if mode == 'free':
            self.settings.download_limit = 0
        if total is not None:
            self.settings.download_limit = int(total)
        self.store.save_settings(self.settings)

    def _schedule_allowed(self):
        return not self.settings.schedule_enabled or time_window(self.settings.schedule_start, self.settings.schedule_end)

    def tick(self):
        now = time.monotonic()
        dt, self.last_tick = now - self.last_tick, now
        notifications = []
        while True:
            try:
                event = self.events.get_nowait()
            except Empty:
                break
            task = self.tasks.get(event['id'])
            if not task:
                continue
            for key, value in event.items():
                if key != 'id' and hasattr(task, key):
                    setattr(task, key, value)
            if task.manual_pause and task.status != 'completed':
                task.status, task.speed = 'paused', 0
            if task.status == 'waiting':
                self.retry_at[task.id] = now + max(5, event.get('retry_after', 0))
            if task.status in ('completed', 'error', 'restart_required'):
                notifications.append(task)
            self.store.save_task(task)
            if task.status == 'completed' and task.kind == 'http':
                receipt_dir = safe_path(Path(task.destination), '.nubetalo-' + task.id)
                try:
                    if receipt_dir.exists() and {p.name for p in receipt_dir.iterdir()} == {'state.json'}:
                        safe_path(receipt_dir, 'state.json').unlink()
                        receipt_dir.rmdir()
                except OSError:
                    pass
        for task_id, (thread, stop) in list(self.workers.items()):
            if not thread.is_alive():
                del self.workers[task_id]
        allowed = self._schedule_allowed()
        torrent_events = self.engine.tick()
        for event in torrent_events:
            task = self.tasks[event['id']]
            if task.status == 'completed':
                self.engine.pause(task.id)
                continue
            previous = task.status
            for key, value in event.items():
                if key != 'id' and hasattr(task, key):
                    setattr(task, key, value)
            if task.status == 'seeding':
                if previous != 'seeding' and not task.completion_notified:
                    notifications.append(task)
                if allowed and not task.manual_pause:
                    task.seeded_seconds += dt
                stop_seed = (not self.settings.seed_enabled or event.get('ratio', 0) >= self.settings.seed_ratio
                             or task.seeded_seconds >= self.settings.seed_minutes * 60)
                if stop_seed:
                    task.status = 'completed'
                    self.engine.pause(task.id)
                    notifications.append(task)
        candidates = sorted((t for t in self.tasks.values() if not t.manual_pause and t.status in ('queued', 'paused', 'downloading', 'checking', 'waiting', 'seeding')),
                            key=lambda t: (-t.priority, t.added))
        active, host_counts = [], {}
        def host_key(task):
            parsed = urlsplit(task.server_origin or task.source)
            return parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)
        if allowed:
            for task in candidates:
                if self.retry_at.get(task.id, 0) > now:
                    continue
                host = host_key(task) if task.kind == 'http' else None
                if host is not None and host_counts.get(host, 0) >= self.settings.connections:
                    continue
                active.append(task)
                if host is not None:
                    host_counts[host] = host_counts.get(host, 0) + 1
                if len(active) >= self.settings.max_active:
                    break
        streams = {t.id: max(1, self.settings.connections // host_counts[host_key(t)]) for t in active if t.kind == 'http'}
        active_ids = {t.id for t in active}
        for task_id, (thread, stop) in self.workers.items():
            # Reducing actual parallelism requires a safe range restart. A single
            # non-resumable transfer must keep its connection when peers join.
            reduce_streams = task_id in streams and self.tasks[task_id].http_streams > streams[task_id]
            if task_id not in active_ids or reduce_streams:
                stop.set()
        for task in self.tasks.values():
            if task.kind == 'torrent' and task.id in self.engine.handles and task.selected is None:
                if allowed and not task.manual_pause and task.status not in ('error', 'completed'):
                    self.engine.resume(task.id)
                else:
                    self.engine.pause(task.id)
            if task.kind == 'torrent' and task.id in self.engine.handles and task.selected is not None:
                if task.id in active_ids:
                    self.engine.resume(task.id)
                else:
                    self.engine.pause(task.id)
            if not allowed and not task.manual_pause and task.status == 'paused':
                task.status = 'queued'
        cap = self.settings.download_limit
        if self.settings.alternate_limit and time_window(self.settings.alternate_start, self.settings.alternate_end):
            cap = self.settings.alternate_limit
        # Stopping HTTP workers still consume their allocation until they actually stop.
        consumers = list({t.id: t for t in active + [self.tasks[k] for k in self.workers]}.values())
        weights = [8 if t.priority == 2 else 1 if t.priority == 0 else 2 for t in consumers] if self.settings.bandwidth_mode == 'priority' else None
        rates = allocate_limits(cap, [t.limit for t in consumers], weights)
        self.rates = {t.id: rate for t, rate in zip(consumers, rates)}
        torrent_rates = {t.id: self.rates[t.id] for t in consumers if t.kind == 'torrent'}
        self.engine.set_limits(sum(torrent_rates.values()) if cap else 0, self.settings.upload_limit, torrent_rates)
        for task in active:
            if task.kind == 'http' and task.id not in self.workers:
                stop = threading.Event()
                worker = HttpWorker(task, self.events, stop, lambda key=task.id: self.rates.get(key, 0), self.settings.connections, streams[task.id])
                thread = threading.Thread(target=worker.run, name='http-' + task.id, daemon=True)
                self.workers[task.id] = (thread, stop)
                task.status = 'downloading'
                task.http_streams = 0
                thread.start()
        # Pauses due only to queue/schedule return to admission, never manual resumes.
        for task in self.tasks.values():
            if task.status == 'paused' and not task.manual_pause and task.id not in self.workers:
                task.status = 'queued'
        if now - self.last_saved > 2:
            for task in self.tasks.values():
                self.store.save_task(task)
            self.last_saved = now
        return notifications

    def close(self):
        for thread, stop in self.workers.values():
            stop.set()
        for thread, stop in self.workers.values():
            thread.join(timeout=18)
        self.engine.close()
        for task in self.tasks.values():
            self.store.save_task(task)
        self.store.save_settings(self.settings)
        self.store.close()
