from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig
from .errors import KbError
from .ignore import IgnoreMatcher
from .security import blocked_by_filename, detect_secret, looks_binary


@dataclass
class SourceFile:
    path: Path
    rel_path: str
    size: int
    mtime_ns: int
    content_hash: str
    encoding: str
    text: str
    secret_hits: list[str]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_paths(config: AppConfig) -> list[Path]:
    matcher = IgnoreMatcher.from_files(
        config.root,
        config.index.exclude + config.security.blocked_file_patterns,
        hidden_files=config.index.hidden_files,
    )
    paths: list[Path] = []
    for p in config.root.rglob("*"):
        try:
            if not p.is_file():
                continue
            if p.is_symlink() and not config.index.follow_symlinks:
                continue
            if matcher.is_ignored(p):
                continue
            stat = p.stat()
            if stat.st_size > config.index.max_file_bytes:
                continue
            if config.security.block_secret_files and blocked_by_filename(p, config.security):
                continue
            if not _matches_include(config, p):
                continue
            paths.append(p)
        except (OSError, PermissionError):
            continue
    return sorted(paths)


def _matches_include(config: AppConfig, path: Path) -> bool:
    import fnmatch
    rel = path.relative_to(config.root).as_posix()
    return any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(path.name, pat) for pat in config.index.include)


def read_source_file(config: AppConfig, path: Path) -> SourceFile | None:
    data = path.read_bytes()
    if looks_binary(data[:4096]):
        return None
    encoding = "utf-8"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            encoding = "utf-8-sig"
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise KbError("KB007", f"{path}: {exc}", cause=exc) from exc
    secret_hits = detect_secret(text) if config.security.secret_scan else []
    if secret_hits and not config.security.allow_secrets:
        # Skip instead of hard-failing full index. The skipped file is reported by status/doctor.
        return None
    stat = path.stat()
    return SourceFile(
        path=path,
        rel_path=path.relative_to(config.root).as_posix(),
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        content_hash=sha256_bytes(data),
        encoding=encoding,
        text=text,
        secret_hits=secret_hits,
    )
