from pathlib import Path
import shutil

root = Path(__file__).resolve().parent.parent
target = root / 'build/legal-licenses'
for source in (root / 'licenses').rglob('*'):
    if not source.is_file():
        continue
    if 'upstream' in source.parts and source.suffix.lower() not in ('', '.txt', '.md', '.rst', '.html'):
        continue
    destination = target / source.relative_to(root / 'licenses')
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
print('Release license texts staged')
