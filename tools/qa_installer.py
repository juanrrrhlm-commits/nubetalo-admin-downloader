"""Build an identity-isolated copy for testing beside an existing user install."""
from pathlib import Path
import os
import subprocess

root = Path(__file__).resolve().parent.parent
source = (root / 'installer/setup.iss').read_text(encoding='utf-8')
changes = {
    'AppId={{A6CA77C2-47DC-43AC-9A26-26B0D18C055C}': 'AppId={{F9AAB43B-BB33-45E1-A1E2-125FA7EA234D}',
    'DefaultGroupName=Nubetalo': 'DefaultGroupName=Nubetalo QA',
    'OutputBaseFilename={#AppName}-Setup-{#AppVersion}': 'OutputBaseFilename={#AppName}-Setup-{#AppVersion}-QA',
    'Name: "{autodesktop}\\{#AppName}"': 'Name: "{autodesktop}\\{#AppName} QA"',
}
for old, new in changes.items():
    assert source.count(old) == 1, old
    source = source.replace(old, new)
target = root / 'test-output/setup-qa.iss'
target.write_text(source, encoding='utf-8')
compiler = Path(os.environ['LOCALAPPDATA']) / 'Programs/Inno Setup 6/ISCC.exe'
with (root / 'test-output/installer-qa.log').open('w', encoding='utf-8') as log:
    result = subprocess.run([str(compiler), str(target)], stdout=log, stderr=subprocess.STDOUT)
assert result.returncode == 0
print('QA installer exit0; only ID, shortcut/group and output name differ', flush=True)
