from tools.package_config import filter_binaries


def test_vendor_icu_alias_cannot_shadow_windows_icu():
    items = [('icuuc.dll', 'vendor/icuuc.dll', 'BINARY'),
             ('icudt78.dll', 'vendor/icudt78.dll', 'BINARY'),
             ('pycurl.libs/icuuc78-hash.dll', 'vendor/icuuc78-hash.dll', 'BINARY'),
             ('PySide6/Qt6Core.dll', 'Qt6Core.dll', 'BINARY')]
    filtered = filter_binaries(items)
    assert len(filtered) == 2
    assert filtered[0][0].startswith('pycurl.libs/')
