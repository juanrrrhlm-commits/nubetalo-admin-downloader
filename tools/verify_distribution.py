"""Exercise the built executable and installer in explicit test-only directories."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import ctypes
import winreg
import argparse
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nubetalo.store import Store
from nubetalo.domain import Settings

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--qa-installer', type=Path)
args = parser.parse_args()
results = {}
run_dir = Path(tempfile.mkdtemp(prefix='distribution-0.3.0-', dir=root / 'test-output'))
desktop_buffer = ctypes.create_unicode_buffer(32768)
assert ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, desktop_buffer) == 0
shortcut = Path(desktop_buffer.value) / ('Nubetalo Admin Downloader QA.lnk' if args.qa_installer else 'Nubetalo Admin Downloader.lnk')
assert not shortcut.exists(), 'Do not overwrite an existing user shortcut during verification'
protected = [Path(os.environ['LOCALAPPDATA']) / 'Programs/Nubetalo Admin Downloader/Nubetalo Admin Downloader.exe',
             Path(desktop_buffer.value) / 'Nubetalo Admin Downloader.lnk'] if args.qa_installer else []
protected_hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.exists()}
if not args.qa_installer:
    assert not (Path(os.environ['LOCALAPPDATA']) / 'Programs/Nubetalo Admin Downloader/Nubetalo Admin Downloader.exe').exists(), 'Do not replace a user installation during verification'
install_id = '{F9AAB43B-BB33-45E1-A1E2-125FA7EA234D}' if args.qa_installer else '{A6CA77C2-47DC-43AC-9A26-26B0D18C055C}'
try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\' + install_id + '_is1')
except FileNotFoundError:
    pass
else:
    key.Close()
    raise AssertionError('Existing installation registry entry; do not overwrite it for verification')


def smoke(exe, name, scale=None):
    data = run_dir / name
    downloads = data / 'downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    store = Store(data / 'state.db')
    store.save_settings(Settings(folder=str(downloads)))
    store.close()
    env = os.environ.copy()
    if scale:
        env['QT_SCALE_FACTOR'] = scale
    completed = subprocess.run([str(exe), '--data-dir', str(data), '--smoke-test', 'https://curl.se/robots.txt'],
                               timeout=45, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    assert completed.returncode == 0, (name, completed.returncode)
    assert (data / 'smoke.png').exists(), name
    store = Store(data / 'state.db')
    tasks = store.load_tasks()
    store.close()
    assert len(tasks) == 1 and tasks[0].status == 'completed', [(t.status,t.error) for t in tasks]
    body = (downloads / 'robots.txt').read_bytes()
    assert body == (root / 'test-output/https/robots.txt').read_bytes()
    results[name] = dict(exit=completed.returncode, downloaded=len(body), sha256=hashlib.sha256(body).hexdigest(), scale=scale or 'system')
    print('PASS', name, flush=True)


smoke(root / 'dist/Nubetalo Admin Downloader/Nubetalo Admin Downloader.exe', 'portable-final')
setup = args.qa_installer or root / 'installer/output/Nubetalo Admin Downloader-Setup-0.3.0.exe'
install_dir = run_dir / 'installed'
run = subprocess.run([str(setup), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
                      '/DIR=' + str(install_dir), '/LOG=' + str(run_dir / 'install.log')],
                     timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
assert run.returncode == 0, run.returncode
results['installation'] = run.returncode
assert shortcut.exists(), 'Default desktop shortcut missing'
results['default_desktop_shortcut'] = True
print('PASS installation', flush=True)
smoke(install_dir / 'Nubetalo Admin Downloader.exe', 'installed-final', scale='2')
uninstaller = install_dir / 'unins000.exe'
run = subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                      '/LOG=' + str(run_dir / 'uninstall.log')], timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
assert run.returncode == 0 and not (install_dir / 'Nubetalo Admin Downloader.exe').exists()
assert not shortcut.exists()
assert (run_dir / 'installed-final/downloads/robots.txt').exists()
results['uninstallation_preserves_downloads'] = True
for path, expected in protected_hashes.items():
    assert path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Existing user installation changed'
results['isolated_qa_identity'] = bool(args.qa_installer)
results['existing_user_installation_preserved'] = bool(protected_hashes)
(root / 'test-output/distribution-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
(run_dir / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print('PASS uninstallation; downloads preserved', flush=True)
