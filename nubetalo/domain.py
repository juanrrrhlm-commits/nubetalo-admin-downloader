from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit
import os
import re
import uuid

APP_NAME = 'Nubetalo Admin Downloader'
DONATE_URL = ('https://www.paypal.com/donate/?business=juan.rodriguez.roman777%40gmail.com'
              '&currency_code=USD&item_name=Nubetalo+Admin+Downloader')


def validate_url(url: str) -> str:
    if len(url) > 16384 or any(ord(c) < 32 for c in url) or '\\' in url:
        raise ValueError('URL inválida / Invalid URL')
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Solo enlaces HTTP/HTTPS sin credenciales / HTTP(S) only')
    _ = p.port
    return url


def safe_path(root: Path, name: str) -> Path:
    root = Path(root).absolute()
    parts = name.replace('\\', '/').split('/')
    if not name or PureWindowsPath(name).is_absolute() or any(
        not x or x in ('.', '..') or re.search(r'[<>:"|?*\x00-\x1f]', x)
        or x.endswith(('.', ' ')) or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', x, re.I)
        for x in parts
    ):
        raise ValueError('Nombre o ruta no segura / Unsafe filename')
    result = root.joinpath(*parts)
    # Check every existing ancestor, including the chosen destination itself.
    for item in (result, *result.parents):
        if item.exists() or item.is_symlink():
            st = item.lstat()
            if item.is_symlink() or getattr(st, 'st_file_attributes', 0) & 0x400:
                raise ValueError('No se permiten enlaces de carpetas / Linked paths disallowed')
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('Ruta fuera del destino / Path escapes destination')
    return result


def time_window(start: str, end: str, now: datetime | None = None) -> bool:
    minute = (now or datetime.now()).strftime('%H:%M')
    return start == end or (start <= minute < end if start < end else minute >= start or minute < end)


@dataclass
class Task:
    source: str
    destination: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    kind: str = 'http'
    name: str = ''
    status: str = 'queued'
    manual_pause: bool = False
    total: int = 0
    done: int = 0
    speed: int = 0
    upload_speed: int = 0
    error: str = ''
    server_notice: str = ''
    server_origin: str = ''
    http_streams: int = 0
    etag: str = ''
    modified: str = ''
    checksum: str = ''
    priority: int = 1
    limit: int = 0
    selected: list[int] | None = None
    file_priorities: dict[str, int] = field(default_factory=dict)
    verified: bool = False
    completion_notified: bool = False
    peers: int = 0
    seeded_seconds: float = 0
    torrent_path: str = ''
    added: str = field(default_factory=lambda: datetime.now().isoformat())

    def data(self) -> dict:
        return asdict(self)


@dataclass
class Settings:
    folder: str = field(default_factory=lambda: str(Path.home() / 'Downloads'))
    language: str = 'es'
    download_limit: int = 0
    upload_limit: int = 0
    bandwidth_mode: str = 'free'
    max_active: int = 3
    connections: int = 4
    schedule_enabled: bool = False
    schedule_start: str = '00:00'
    schedule_end: str = '00:00'
    alternate_limit: int = 0
    alternate_start: str = '22:00'
    alternate_end: str = '06:00'
    seed_ratio: float = 1.0
    seed_minutes: int = 60
    seed_enabled: bool = True
    minimize_tray: bool = True
    completion_sound: bool = True
    completion_notice: bool = True


def data_directory() -> Path:
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Nubetalo Admin Downloader'
