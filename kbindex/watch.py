from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .config import AppConfig
from .indexer import sync
from .logging_utils import command_logger
from .status import status


def watch(config: AppConfig, *, once: bool = False, on_sync: Callable[[object], None] | None = None) -> None:
    logger = command_logger(config.db, "watch", config.security.redact_logs)
    last_run = 0.0
    try:
        from watchfiles import watch as wf_watch
        for changes in wf_watch(str(config.root), debounce=int(config.runtime.watch_debounce_seconds * 1000)):
            logger.event("changes_detected", count=len(changes))
            now = time.time()
            if now - last_run < config.runtime.watch_batch_interval_seconds:
                time.sleep(config.runtime.watch_batch_interval_seconds - (now - last_run))
            result = sync(config)
            last_run = time.time()
            if on_sync:
                on_sync(result)
            if once:
                return
    except ImportError:
        _polling_watch(config, once=once, on_sync=on_sync)


def _polling_watch(config: AppConfig, *, once: bool, on_sync: Callable[[object], None] | None) -> None:
    snapshot = _snapshot(config.root)
    while True:
        time.sleep(config.runtime.watch_batch_interval_seconds)
        new_snapshot = _snapshot(config.root)
        if new_snapshot != snapshot:
            result = sync(config)
            if on_sync:
                on_sync(result)
            snapshot = new_snapshot
            if once:
                return


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    out = {}
    for p in root.rglob("*"):
        if p.is_file():
            try:
                st = p.stat()
                out[p.as_posix()] = (st.st_size, st.st_mtime_ns)
            except OSError:
                pass
    return out
