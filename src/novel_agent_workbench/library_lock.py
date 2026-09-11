"""One writable desktop session per resolved project library; released by the OS."""
from __future__ import annotations

import ctypes
from hashlib import sha256
import os
from pathlib import Path


class LibraryInUseError(RuntimeError):
    pass


class LibraryLease:
    def __init__(self, root: Path, handle: int):
        self.root = root
        self._handle = handle

    @classmethod
    def acquire(cls, projects_root: Path) -> "LibraryLease":
        root = projects_root.expanduser().resolve()
        message = f"这个项目库已在另一个窗口中使用，请回到已有窗口，或先关闭它。\n\n{root}"
        if os.name == "nt":
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create = kernel.CreateMutexW
            create.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            create.restype = wintypes.HANDLE
            name = "Local\\NovelAgentWorkbench-Library-" + sha256(os.path.normcase(str(root)).encode("utf-8")).hexdigest()
            ctypes.set_last_error(0)
            handle = create(None, False, name)
            error = ctypes.get_last_error()
            if not handle:
                raise ctypes.WinError(error)
            lease = cls(root, handle)
            if error == 183:  # ERROR_ALREADY_EXISTS, including another handle in this process.
                lease.close()
                raise LibraryInUseError(message)
            return lease
        import fcntl
        root.mkdir(parents=True, exist_ok=True)
        handle = os.open(root / ".workbench-library.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(handle)
            raise LibraryInUseError(message) from exc
        return cls(root, handle)

    def close(self) -> None:
        if self._handle is None:
            return
        handle, self._handle = self._handle, None
        if os.name == "nt":
            from ctypes import wintypes
            close = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
            close.argtypes = (wintypes.HANDLE,)
            close.restype = wintypes.BOOL
            close(handle)
        else:
            os.close(handle)

    def __enter__(self) -> "LibraryLease":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


def show_startup_message(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, "小说创作工作台", 0x40)
    else:
        print(message)
