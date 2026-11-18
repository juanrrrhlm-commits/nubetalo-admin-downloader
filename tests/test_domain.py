from datetime import datetime
from pathlib import Path
import pytest
from nubetalo.domain import validate_url, safe_path, time_window, Task, Settings


@pytest.mark.parametrize('url', ['file:///C:/x', 'ftp://host/x', 'https://a\nb/', 'https://user:pw@example.com/a', 'https:///x'])  # pragma: allowlist secret - invalid fixture
def test_reject_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize('name', ['../x', '/x', 'C:/x', 'CON', 'a:stream', 'a/../../x', 'a.', 'LPT1.txt'])
def test_reject_unsafe_paths(tmp_path, name):
    with pytest.raises(ValueError):
        safe_path(tmp_path, name)


def test_nested_safe_path(tmp_path):
    assert safe_path(tmp_path, 'folder/file.bin') == tmp_path / 'folder/file.bin'


def test_midnight_window():
    assert time_window('22:00', '06:00', datetime(2026, 11, 17, 23))
    assert not time_window('22:00', '06:00', datetime(2026, 11, 17, 12))


def test_reparse_rejected(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    link = tmp_path / 'link'
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('symlink privilege unavailable')
    with pytest.raises(ValueError):
        safe_path(tmp_path, 'link/other')
