"""Preserve upstream license texts and corresponding Qt sources for releases."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
import hashlib
import json
import tarfile
import urllib.request

root = Path(__file__).resolve().parent.parent
out = root / 'dist/third-party-sources'
out.mkdir(parents=True, exist_ok=True)
qt = 'https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/'
sources = [qt + n + '-everywhere-src-6.12.0.tar.xz' for n in ('qtbase', 'qtsvg', 'qtimageformats')]
sources.append('https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.tar.xz')


def retrieve(url):
    name = url.rsplit('/', 1)[-1]
    path = out / name
    if not path.exists():
        with urllib.request.urlopen(url, timeout=90) as response:
            if not response.url.startswith('https://'):
                raise ValueError('Insecure source redirect')
            with path.with_suffix(path.suffix + '.part').open('wb') as target:
                while chunk := response.read(1024 * 1024):
                    target.write(chunk)
        path.with_suffix(path.suffix + '.part').replace(path)
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            # Never extract archive paths, symlinks or executables.
            relative = PurePosixPath(member.name)
            if not member.isfile() or member.size > 1024 * 1024:
                continue
            if relative.suffix.lower() not in ('', '.txt', '.md', '.rst', '.html'):
                continue
            if 'LICENSES' not in relative.parts and not relative.name.lower().startswith(('license', 'copying', 'copyright')):
                continue
            if '..' in relative.parts or relative.is_absolute():
                raise ValueError('Unsafe source archive path')
            target = root / 'licenses/upstream' / name.removesuffix('.tar.xz') / Path(*relative.parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
    print('Source and notices collected:', name, flush=True)
    return dict(file=name, url=url, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)


with ThreadPoolExecutor(max_workers=4) as pool:
    manifest = list(pool.map(retrieve, sources))
(root / 'docs/DEPENDENCY_SOURCES.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
(out / 'SHA256SUMS.txt').write_text(''.join(f'{x["sha256"]}  {x["file"]}\n' for x in manifest), encoding='utf-8')

license_urls = {
    'OpenSSL-Apache-2.0.txt': 'https://raw.githubusercontent.com/openssl/openssl/openssl-3.6.5/LICENSE.txt',
    'ICU-Unicode.txt': 'https://raw.githubusercontent.com/unicode-org/icu/release-78.1/LICENSE',
    'brotli-MIT.txt': 'https://raw.githubusercontent.com/google/brotli/v1.2.1/LICENSE',
    'libpsl-MIT.txt': 'https://raw.githubusercontent.com/rockdaboot/libpsl/0.21.5/COPYING',
    'libssh2-BSD.txt': 'https://raw.githubusercontent.com/libssh2/libssh2/libssh2-1.11.1/COPYING',
    'nghttp2-MIT.txt': 'https://raw.githubusercontent.com/nghttp2/nghttp2/v1.70.0/COPYING',
    'zlib.txt': 'https://raw.githubusercontent.com/madler/zlib/v1.3.2/LICENSE',
    'libffi-MIT.txt': 'https://raw.githubusercontent.com/libffi/libffi/v3.4.8/LICENSE',
    'PyInstaller-exception.txt': 'https://raw.githubusercontent.com/pyinstaller/pyinstaller/v6.22.3/COPYING.txt',
}
failures = []
for name, url in license_urls.items():
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            body = response.read()
        (root / 'licenses' / name).write_bytes(body)
        print('Notice collected:', name, flush=True)
    except OSError:
        failures.append(name)
if failures:
    raise RuntimeError('Missing notices: ' + ', '.join(failures))
