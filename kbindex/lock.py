from __future__ import annotations

import os
import time
from pathlib import Path

from .errors import KbError


class FileLock:
    def __init__(self, path: Path, timeout_seconds: int = 120, stale_seconds: int = 7200):
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.stale_seconds = stale_seconds
        self.fd: int | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, f"pid={os.getpid()} ts={time.time()}\n".encode())
                return self
            except FileExistsError:
                if self._is_stale():
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                if time.monotonic() - start > self.timeout_seconds:
                    raise KbError("KB005", f"lock file exists: {self.path}")
                time.sleep(0.2)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            finally:
                self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _is_stale(self) -> bool:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return False
        return (time.time() - stat.st_mtime) > self.stale_seconds
