from __future__ import annotations

import fnmatch
from pathlib import Path


class IgnoreMatcher:
    def __init__(self, root: Path, patterns: list[str], hidden_files: bool = False):
        self.root = root
        self.patterns = [p.strip() for p in patterns if p.strip() and not p.strip().startswith("#")]
        self.hidden_files = hidden_files
        self._pathspec = None
        try:
            import pathspec  # type: ignore
            self._pathspec = pathspec.PathSpec.from_lines("gitwildmatch", self.patterns)
        except Exception:
            self._pathspec = None

    @classmethod
    def from_files(cls, root: Path, patterns: list[str], hidden_files: bool) -> "IgnoreMatcher":
        merged = list(patterns)
        for name in [".gitignore", ".kbignore"]:
            p = root / name
            if p.exists():
                try:
                    merged.extend(p.read_text(encoding="utf-8").splitlines())
                except UnicodeDecodeError:
                    pass
        return cls(root, merged, hidden_files)

    def is_ignored(self, path: Path) -> bool:
        try:
            rel = path.relative_to(self.root).as_posix()
        except ValueError:
            rel = path.as_posix()
        if not self.hidden_files:
            if any(part.startswith(".") and part not in {"."} for part in Path(rel).parts):
                # Allow explicit .kbignore and .github instructions if user includes them.
                if not rel.startswith(".github/") and rel not in {".kbignore"}:
                    return True
        if self._pathspec is not None:
            return bool(self._pathspec.match_file(rel))
        return any(self._match(pattern, rel) for pattern in self.patterns)

    def _match(self, pattern: str, rel: str) -> bool:
        pattern = pattern.strip("/")
        if pattern.endswith("/**"):
            prefix = pattern[:-3].strip("/")
            return rel == prefix or rel.startswith(prefix + "/")
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(Path(rel).name, pattern):
            return True
        if "/" not in pattern and any(fnmatch.fnmatch(part, pattern) for part in Path(rel).parts):
            return True
        return False
