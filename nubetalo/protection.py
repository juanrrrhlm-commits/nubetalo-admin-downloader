"""User-bound Windows DPAPI protection for local private application records."""
import ctypes
from ctypes import wintypes
import sys
import os

PREFIX = b'Nubetalo-DPAPI-1\0'


class DataBlob(ctypes.Structure):
    _fields_ = [('length', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data, decrypt=False):
    if sys.platform != 'win32':
        raise OSError('La protección de datos requiere Windows / Data protection requires Windows')
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    source = DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = DataBlob()
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
    function.restype = wintypes.BOOL
    # UI_FORBIDDEN; deliberately no LOCAL_MACHINE flag or embedded password.
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise OSError('No se pudieron proteger o leer los datos locales del usuario / Cannot protect or read user data')
    try:
        return ctypes.string_at(output.data, output.length)
    finally:
        kernel32.LocalFree(output.data)


def protect(data: bytes) -> bytes:
    return PREFIX + _crypt(data)


def unprotect(data: bytes) -> bytes:
    if not data.startswith(PREFIX):
        raise OSError('Formato de datos protegidos no válido / Invalid protected data')
    return _crypt(data[len(PREFIX):], decrypt=True)


def read_private(data: bytes) -> bytes:
    """Read legacy local files once; new writes always use protection."""
    return unprotect(data) if data.startswith(PREFIX) else data


def write_private(path, data: bytes):
    temporary = path.with_name(path.name + '.new')
    with open(temporary, 'wb') as output:
        output.write(protect(data))
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
