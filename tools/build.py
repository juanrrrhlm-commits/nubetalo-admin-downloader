from pathlib import Path
import hashlib
import os
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
os.chdir(root)
(root / 'test-output').mkdir(exist_ok=True)


def run(command, log):
    with open(root / 'test-output' / log, 'w', encoding='utf-8') as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        print((root / 'test-output' / log).read_text(encoding='utf-8', errors='replace')[-5000:])
        raise SystemExit(result.returncode)
    print('PASS:', log, flush=True)


run([sys.executable, '-m', 'pytest', 'tests', '-q', '--disable-warnings'], 'tests.log')
run([sys.executable, '-m', 'compileall', '-q', 'nubetalo', 'main.py'], 'compile.log')
run([sys.executable, 'tools/legal_page.py'], 'legal.log')
run([sys.executable, 'tools/stage_licenses.py'], 'notices.log')
run([sys.executable, '-m', 'PyInstaller', '--noconfirm', 'tools/downloader.spec'], 'package.log')
run([sys.executable, 'tools/source_zip.py'], 'source.log')
compiler = Path(os.environ['LOCALAPPDATA']) / 'Programs/Inno Setup 6/ISCC.exe'
run([str(compiler), 'installer/setup.iss'], 'installer.log')
setup = root / 'installer/output/Nubetalo Admin Downloader-Setup-0.3.0.exe'
with setup.open('rb') as source:
    digest = hashlib.file_digest(source, 'sha256').hexdigest()
(setup.parent / 'SHA256SUMS.txt').write_text(f'{digest}  {setup.name}\n', encoding='utf-8')
print(setup, setup.stat().st_size, digest)
