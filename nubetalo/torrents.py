"""Libtorrent session; payload is gated on explicit content selection."""
from pathlib import Path
import os
import time
import libtorrent as lt
from .domain import Task, safe_path
from .protection import PREFIX, protect, read_private, write_private


class TorrentEngine:
    def __init__(self, state_dir: Path, local_only=False):
        self.root = state_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self.handles, self.tasks = {}, {}
        self.validated = set()
        self.validation_errors = {}
        self.flush_pending, self.flushed, self.saved = set(), set(), set()
        self.last_save = time.monotonic()
        self.session = lt.session({
            'listen_interfaces': '127.0.0.1:0' if local_only else '0.0.0.0:0,[::]:0',
            'enable_dht': not local_only, 'enable_lsd': False,
            'enable_upnp': False, 'enable_natpmp': False,
            'max_metadata_size': 4 * 1024 * 1024,
            'alert_mask': lt.alert.category_t.status_notification | lt.alert.category_t.error_notification | lt.alert.category_t.storage_notification,
        })

    @staticmethod
    def validate_info(info, destination):
        fs = info.files()
        if fs.num_files() > 10000:
            raise ValueError('Torrent con demasiados archivos / Too many files')
        for i in range(fs.num_files()):
            if fs.file_flags(i) & lt.file_storage.flag_symlink:
                raise ValueError('Torrent con enlaces simbólicos / Torrent contains symlinks')
            safe_path(Path(destination), fs.file_path(i))

    def add(self, task: Task, metadata_allowed=True):
        cache_write = None
        resume = self.root / f'{task.id}.resume'
        if resume.exists():
            stored = resume.read_bytes()
            raw = read_private(stored)
            params = lt.read_resume_data(raw)
            if not stored.startswith(PREFIX):
                write_private(resume, raw)
        elif task.source.startswith('magnet:?'):
            if len(task.source) > 16384:
                raise ValueError('Magnet demasiado largo / Magnet too long')
            params = lt.parse_magnet_uri(task.source)
        else:
            params = lt.add_torrent_params()
            source = Path(task.torrent_path or task.source)
            if source.stat().st_size > 4 * 1024 * 1024:
                raise ValueError('Archivo torrent demasiado grande / Torrent too large')
            raw = read_private(source.read_bytes())
            params.ti = lt.torrent_info(lt.bdecode(raw))
            cached = self.root / f'{task.id}.torrent'
            if source.absolute() != cached.absolute() or not source.read_bytes().startswith(PREFIX):
                cache_write = (cached, raw)
            task.torrent_path = str(cached)
        if params.ti:
            self.validate_info(params.ti, task.destination)
        if cache_write:
            write_private(*cache_write)
        params.save_path = task.destination
        params.flags &= ~lt.torrent_flags.auto_managed
        params.flags |= lt.torrent_flags.paused
        params.flags |= lt.torrent_flags.duplicate_is_error
        if task.selected is None:
            params.flags |= lt.torrent_flags.upload_mode
            if params.ti:
                params.file_priorities = [0] * params.ti.num_files()
        elif params.ti:
            params.file_priorities = [task.file_priorities.get(str(i), 4) if i in task.selected else 0 for i in range(params.ti.num_files())]
            params.flags &= ~lt.torrent_flags.upload_mode
        handle = self.session.add_torrent(params)
        self.handles[task.id], self.tasks[task.id] = handle, task
        if params.ti:
            self.validated.add(task.id)
        if not params.ti and task.selected is None and not task.manual_pause and metadata_allowed:
            handle.resume()  # Metadata exchange only; upload_mode blocks payload.
        return handle

    def files(self, task_id):
        info = self.handles[task_id].torrent_file()
        if not info:
            return []
        fs = info.files()
        return [dict(index=i, name=fs.file_path(i), size=fs.file_size(i),
                     pad=bool(fs.file_flags(i) & lt.file_storage.flag_pad_file)) for i in range(fs.num_files())]

    def select(self, task_id, indices, priorities=None):
        handle = self.handles[task_id]
        self.validate_info(handle.torrent_file(), self.tasks[task_id].destination)
        files = self.files(task_id)
        allowed = {f['index'] for f in files if not f['pad']}
        if not indices or not set(indices).issubset(allowed):
            raise ValueError('Selecciona al menos un archivo / Select at least one file')
        priorities = priorities or {}
        if any(v not in (1, 4, 7) for v in priorities.values()):
            raise ValueError('Prioridad inválida / Invalid priority')
        handle.prioritize_files([priorities.get(str(f['index']), 4) if f['index'] in indices else 0 for f in files])
        handle.set_upload_mode(False)
        self.tasks[task_id].selected = list(indices)
        self.tasks[task_id].file_priorities = priorities

    def pause(self, task_id):
        if task_id in self.handles:
            self.handles[task_id].pause()

    def resume(self, task_id):
        self.handles[task_id].resume()

    def remove(self, task_id):
        if task_id in self.handles:
            self.session.remove_torrent(self.handles.pop(task_id))
            self.tasks.pop(task_id, None)
            self.validated.discard(task_id)
            self.validation_errors.pop(task_id, None)
        (self.root / f'{task_id}.resume').unlink(missing_ok=True)

    def set_limits(self, download, upload, individual):
        self.session.apply_settings({'download_rate_limit': max(0, download), 'upload_rate_limit': max(0, upload)})
        for task_id, limit in individual.items():
            if task_id in self.handles:
                self.handles[task_id].set_download_limit(limit)

    def alerts(self):
        for alert in self.session.pop_alerts():
            if isinstance(alert, lt.cache_flushed_alert):
                task_id = next((k for k, h in self.handles.items() if h == alert.handle), None)
                if task_id:
                    self.flush_pending.discard(task_id)
                    self.flushed.add(task_id)
            if isinstance(alert, lt.save_resume_data_alert):
                task_id = next((k for k, h in self.handles.items() if h == alert.handle), None)
                if task_id:
                    path = self.root / f'{task_id}.resume'
                    temporary = path.with_suffix('.new')
                    with open(temporary, 'wb') as f:
                        f.write(protect(lt.write_resume_data_buf(alert.params)))
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temporary, path)
                    self.saved.add(task_id)

    def tick(self):
        self.alerts()
        output = []
        for task_id, handle in self.handles.items():
            task = self.tasks[task_id]
            if task_id in self.validation_errors:
                output.append(dict(id=task_id, status='error', error=self.validation_errors[task_id], speed=0))
                continue
            status = handle.status()
            error = status.errc
            if error.value():
                output.append(dict(id=task_id, status='error', error='Error de torrent o disco / Torrent or disk error', speed=0))
                continue
            if status.has_metadata:
                info = handle.torrent_file()
                try:
                    if task_id not in self.validated:
                        self.validate_info(info, task.destination)
                        self.validated.add(task_id)
                except ValueError as exc:
                    handle.pause()
                    self.validation_errors[task_id] = str(exc)
                    output.append(dict(id=task_id, status='error', error=str(exc), speed=0))
                    continue
                name = info.name()
            else:
                name = 'Obteniendo metadatos / Fetching metadata'
            if task.manual_pause:
                state = 'paused'
            elif task.selected is None:
                state = 'selection' if status.has_metadata else 'metadata'
            elif status.paused:
                state = 'queued'
            elif status.is_finished:
                if task_id not in self.flushed and task_id not in self.flush_pending:
                    self.flush_pending.add(task_id)
                    handle.flush_cache()
                state = 'seeding' if task_id in self.flushed else 'checking'
            elif status.state in (lt.torrent_status.checking_files, lt.torrent_status.checking_resume_data):
                state = 'checking'
            else:
                state = 'downloading'
            output.append(dict(id=task_id, status=state, name=name, total=status.total_wanted,
                               done=status.total_wanted_done, speed=status.download_payload_rate,
                               upload_speed=status.upload_payload_rate, peers=status.num_peers,
                               verified=status.is_finished and task_id in self.flushed, ratio=status.all_time_upload / max(1, status.all_time_download)))
        if time.monotonic() - self.last_save > 15:
            self.save()
        return output

    def save(self):
        for handle in self.handles.values():
            if handle.status().has_metadata:
                handle.save_resume_data(lt.save_resume_flags_t.flush_disk_cache | lt.save_resume_flags_t.save_info_dict)
        self.last_save = time.monotonic()

    def close(self):
        self.session.pause()
        self.saved.clear()
        for task_id, handle in self.handles.items():
            if handle.status().has_metadata:
                self.flush_pending.add(task_id)
                self.flushed.discard(task_id)
                handle.flush_cache()
        self.save()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            self.alerts()
            if not self.flush_pending and all(k in self.saved or not h.status().has_metadata for k, h in self.handles.items()):
                break
            time.sleep(.05)
        self.alerts()
