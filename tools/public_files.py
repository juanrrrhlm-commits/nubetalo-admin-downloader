"""Explicit public distribution manifest: no work notes, user data or build logs."""
from pathlib import Path

TOP_LEVEL = ['main.py', 'README.md', 'BUILD.md', 'PRIVACY.md', 'LEGAL.md', 'SECURITY.md',
             'THIRD_PARTY_NOTICES.md', 'LICENSE.txt', 'COPYRIGHT.md', 'CHANGELOG.md',
             'requirements-lock.txt', '.gitignore']
PUBLIC_DOCS = ['docs/SECURITY_AUDIT.md', 'docs/DEPENDENCY_SOURCES.json',
               'docs/img/preview-0.3.0.png', 'docs/img/notification-0.3.0.png', 'docs/img/icon-0.3.0.png']


def public_files(root: Path):
    files = [root / name for name in TOP_LEVEL + PUBLIC_DOCS if (root / name).is_file()]
    for folder in ('nubetalo', 'tests', 'tools', 'assets', 'licenses', 'installer', '.github'):
        for path in (root / folder).rglob('*'):
            if path.is_file() and not any(p in ('__pycache__', 'output', '.pytest_cache') for p in path.relative_to(root).parts):
                if folder == 'tools' and path.name == 'export_public.py':
                    continue
                if folder == 'licenses' and 'upstream' in path.parts and path.suffix.lower() not in ('', '.txt', '.md', '.rst', '.html'):
                    continue
                files.append(path)
    return sorted(set(files))
