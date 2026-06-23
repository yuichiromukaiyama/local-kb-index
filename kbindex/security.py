from __future__ import annotations

import re
from pathlib import Path

from .config import SecurityConfig

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)(client_secret|api[_-]?key|access[_-]?token|refresh[_-]?token|password)\s*[:=]\s*['\"]?[^'\"\s]{12,}"),
    re.compile(r"(?i)DefaultEndpointsProtocol=https;AccountName=.*;AccountKey="),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]


def looks_binary(sample: bytes) -> bool:
    if b"\x00" in sample:
        return True
    if not sample:
        return False
    non_text = sum(1 for b in sample if b < 9 or (b > 13 and b < 32))
    return (non_text / max(len(sample), 1)) > 0.30


def detect_secret(text: str) -> list[str]:
    hits: list[str] = []
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            hits.append(pat.pattern[:80])
    return hits


def blocked_by_filename(path: Path, cfg: SecurityConfig) -> bool:
    import fnmatch
    name = path.name
    rel = path.as_posix()
    return any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel, p) for p in cfg.blocked_file_patterns)
