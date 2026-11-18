from pathlib import Path
import sys
root = Path(SPECPATH).parent
sys.path.insert(0, str(root))
from tools.package_config import filter_binaries

a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=[],
    datas=[(str(root / 'assets'), 'assets'), (str(root / 'build/legal-licenses'), 'licenses')],
    hiddenimports=['libtorrent', 'pycurl'], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['pytest', 'PIL'], noarchive=False, optimize=0)
a.binaries = filter_binaries(a.binaries)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Nubetalo Admin Downloader',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=True, icon=str(root / 'assets/app.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Nubetalo Admin Downloader')
