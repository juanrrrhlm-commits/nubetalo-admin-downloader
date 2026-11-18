from pathlib import PurePosixPath


def filter_binaries(binaries):
    # Qt 6.12 uses Windows native ICU's unversioned API. PyInstaller can collect
    # raw ICU 78 aliases from curl, whose versioned exports break QtCore (WinError127).
    # Keep curl's separately named, delvewheel-patched DLLs in pycurl.libs.
    return [item for item in binaries if not (
        len(PurePosixPath(item[0].replace('\\', '/')).parts) == 1
        and (item[0].lower() == 'icuuc.dll' or item[0].lower().startswith('icudt'))
    )]
