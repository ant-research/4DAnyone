"""Windows sidecar locks, imported only when acquiring a lock on Windows."""

import ctypes
import errno
import msvcrt
import os
from ctypes import wintypes
from pathlib import Path

_GENERIC_READ_WRITE = 0x80000000 | 0x40000000
_OPEN_ALWAYS = 4
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_FILE_ATTRIBUTE_TAG_INFO = 9
_ERROR_SHARING_VIOLATION = 32
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _FileAttributeTagInfo(ctypes.Structure):
    _fields_ = [("attributes", wintypes.DWORD), ("reparse_tag", wintypes.DWORD)]


def open_lock_file(path: Path) -> int:
    """Acquire a nonblocking exclusive handle; os.close releases the reservation.

    Denying read/write/delete sharing prevents concurrent owners and replacement
    of the sidecar. Open reparse points themselves, then reject them through the
    handle so even dangling links cannot create or lock an unrelated target.
    """

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    get_info = kernel32.GetFileInformationByHandleEx
    get_info.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    get_info.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = create_file(str(path), _GENERIC_READ_WRITE, 0, None, _OPEN_ALWAYS, _FILE_FLAG_OPEN_REPARSE_POINT, None)
    if handle == _INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        if error == _ERROR_SHARING_VIOLATION:
            raise BlockingIOError(errno.EAGAIN, "Output lock is already held", str(path))
        raise ctypes.WinError(error)
    try:
        info = _FileAttributeTagInfo()
        if not get_info(handle, _FILE_ATTRIBUTE_TAG_INFO, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise OSError(errno.ELOOP, "Output lock must not be a reparse point", str(path))
        # Ownership transfers to the CRT only on success. The handle was created
        # non-inheritable, so a child process cannot keep its parent's lock alive.
        return msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
    except BaseException:
        close_handle(handle)
        raise
