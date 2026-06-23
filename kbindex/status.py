from __future__ import annotations

from dataclasses import dataclass, field
import time

from .config import AppConfig
from .db import MetadataDb
from .scan import candidate_paths, read_source_file
from .vector_store import VectorStore


@dataclass
class StatusResult:
    root: str
    db: str
    index_exists: bool
    schema_ok: bool
    files: int = 0
    chunks: int = 0
    symbols: int = 0
    edges: int = 0
    vector_rows: int = 0
    new_files: int = 0
    changed_files: int = 0
    deleted_files: int = 0
    skipped_files: int = 0
    stale: bool = False
    embedding_model: str | None = None
    embedding_dim: str | None = None
    last_sync_at: str | None = None
    warnings: list[str] = field(default_factory=list)


def status(config: AppConfig, *, scan: bool = True) -> StatusResult:
    db = MetadataDb(config)
    res = StatusResult(root=str(config.root), db=str(config.db), index_exists=config.sqlite_path.exists(), schema_ok=False)
    if not config.sqlite_path.exists():
        res.warnings.append("index is missing")
        return res
    try:
        db.check_schema()
        res.schema_ok = True
    except Exception as exc:
        res.warnings.append(str(exc))
        return res
    with db.connect() as conn:
        summary = db.file_summary(conn)
        res.files = summary["files"]
        res.chunks = summary["chunks"]
        res.symbols = summary["symbols"]
        res.edges = summary["edges"]
        res.embedding_model = db.get_meta(conn, "embedding_model")
        res.embedding_dim = db.get_meta(conn, "embedding_dim")
        last = db.get_meta(conn, "last_sync_at")
        if last:
            try:
                res.last_sync_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(last)))
            except Exception:
                res.last_sync_at = last
        indexed_rows = {r["path"]: r for r in conn.execute("SELECT * FROM files WHERE deleted_at IS NULL").fetchall()}
    try:
        vs = VectorStore(config)
        res.vector_rows = vs.count()
        if not vs.vector_column_ok():
            res.warnings.append("vector column is missing")
    except Exception as exc:
        res.warnings.append(f"vector store unavailable: {exc}")
    if scan:
        current = {}
        skipped = 0
        for p in candidate_paths(config):
            src = read_source_file(config, p)
            if src is None:
                skipped += 1
                continue
            current[src.rel_path] = src
        indexed_paths = set(indexed_rows.keys())
        current_paths = set(current.keys())
        res.new_files = len(current_paths - indexed_paths)
        res.deleted_files = len(indexed_paths - current_paths)
        changed = 0
        for rel, src in current.items():
            old = indexed_rows.get(rel)
            if old is not None and (str(old["content_hash"]) != src.content_hash or int(old["mtime_ns"]) != src.mtime_ns):
                changed += 1
        res.changed_files = changed
        res.skipped_files = skipped
        res.stale = any([res.new_files, res.deleted_files, res.changed_files])
    return res
