"""Generate a readable, offline privacy and license notice from release documents."""
from pathlib import Path
import html

root = Path(__file__).resolve().parent.parent
parts = []
for name in ('LEGAL.md', 'PRIVACY.md'):
    for line in (root / name).read_text(encoding='utf-8').splitlines():
        if line.startswith('# '):
            parts.append('<h1>' + html.escape(line[2:]) + '</h1>')
        elif line.startswith('## '):
            parts.append('<h2>' + html.escape(line[3:]) + '</h2>')
        elif line:
            parts.append('<p>' + html.escape(line).replace('**', '') + '</p>')
page = '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
page += '<title>Nubetalo — Privacidad y licencias</title><style>body{max-width:820px;margin:36px auto;padding:0 24px;background:#080c0a;color:#edf7f0;font:16px/1.6 system-ui}h1,h2{color:#57ff93}p{margin:.4em 0}</style>'
page += '<body>' + '\n'.join(parts) + '</body></html>'
(root / 'assets/legal.html').write_text(page, encoding='utf-8')
print('Offline legal notice generated')
