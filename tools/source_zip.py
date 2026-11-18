from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from public_files import public_files

root = Path(__file__).resolve().parent.parent
output = root / 'dist' / 'Nubetalo Admin Downloader-Source-0.3.0.zip'
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for path in public_files(root):
        archive.write(path, path.relative_to(root))
print(output)
