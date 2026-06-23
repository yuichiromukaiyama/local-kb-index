from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .chunkers import Chunk, chunk_source, detect_language
from .config import AppConfig
from .db import MetadataDb
from .embedding import EmbeddingProvider
from .errors import KbError
from .lock import FileLock
from .logging_utils import command_logger
from .scan import SourceFile, candidate_paths, read_source_file
from .vector_store import VectorStore


@dataclass
class IndexResult:
    command: str
    scanned_files: int = 0
    indexed_files: int = 0
    changed_files: int = 0
    new_files: int = 0
    deleted_files: int = 0
    skipped_files: int = 0
    chunks: int = 0
    symbols: int = 0
    edges: int = 0
    duration_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)


def index_full(config: AppConfig, *, force: bool = False) -> IndexResult:
    start = time.time()
    logger = command_logger(config.db, "index", config.security.redact_logs)
    with FileLock(config.lock_path, config.runtime.lock_timeout_seconds, config.runtime.stale_lock_seconds):
        db = MetadataDb(config)
        if force and config.db.exists():
            _remove_db(config)
        config.db.mkdir(parents=True, exist_ok=True)
        config.logs_dir.mkdir(parents=True, exist_ok=True)
        db.initialize()
        embedder = EmbeddingProvider(config)
        dim = embedder.dimension()
        vs = VectorStore(config)
        if force:
            vs.drop_table()
        vs.ensure_table(dim)
        result = _sync_impl(config, command="index", full=True, db=db, embedder=embedder, vs=vs)
    result.duration_seconds = time.time() - start
    logger.event("index_complete", **result.__dict__)
    return result


def sync(config: AppConfig) -> IndexResult:
    start = time.time()
    logger = command_logger(config.db, "sync", config.security.redact_logs)
    with FileLock(config.lock_path, config.runtime.lock_timeout_seconds, config.runtime.stale_lock_seconds):
        db = MetadataDb(config)
        db.check_schema(allow_missing=False)
        embedder = EmbeddingProvider(config)
        dim = embedder.dimension()
        vs = VectorStore(config)
        vs.ensure_table(dim)
        result = _sync_impl(config, command="sync", full=False, db=db, embedder=embedder, vs=vs)
    result.duration_seconds = time.time() - start
    logger.event("sync_complete", **result.__dict__)
    return result


def rebuild(config: AppConfig, *, force: bool = False) -> IndexResult:
    return index_full(config, force=True or force)


def prune(config: AppConfig) -> IndexResult:
    start = time.time()
    db = MetadataDb(config)
    db.check_schema()
    vs = VectorStore(config)
    result = IndexResult(command="prune")
    with FileLock(config.lock_path, config.runtime.lock_timeout_seconds, config.runtime.stale_lock_seconds):
        existing = {p.relative_to(config.root).as_posix() for p in candidate_paths(config)}
        with db.transaction() as conn:
            indexed = db.all_indexed_paths(conn)
            deleted = sorted(indexed - existing)
            for path in deleted:
                db.mark_file_deleted(conn, path)
            db.set_meta(conn, "last_prune_at", str(time.time()))
            result.deleted_files = len(deleted)
        vs.delete_paths(deleted)
    result.duration_seconds = time.time() - start
    return result


def _sync_impl(config: AppConfig, *, command: Literal["index", "sync"], full: bool, db: MetadataDb, embedder: EmbeddingProvider, vs: VectorStore) -> IndexResult:
    result = IndexResult(command=command)
    paths = candidate_paths(config)
    result.scanned_files = len(paths)
    current_by_path: dict[str, SourceFile] = {}
    skipped = 0
    for path in paths:
        try:
            src = read_source_file(config, path)
            if src is None:
                skipped += 1
                continue
            current_by_path[src.rel_path] = src
        except KbError:
            skipped += 1
    result.skipped_files = skipped
    git_commit = _git_commit(config.root)

    with db.connect() as conn:
        indexed_rows = {r["path"]: r for r in conn.execute("SELECT * FROM files WHERE deleted_at IS NULL").fetchall()}
    indexed_paths = set(indexed_rows.keys())
    current_paths = set(current_by_path.keys())
    deleted_paths = sorted(indexed_paths - current_paths)
    changed_paths: list[str] = []
    new_paths: list[str] = []
    for rel, src in current_by_path.items():
        old = indexed_rows.get(rel)
        if old is None:
            new_paths.append(rel)
            changed_paths.append(rel)
        elif full or str(old["content_hash"]) != src.content_hash or int(old["mtime_ns"]) != src.mtime_ns:
            changed_paths.append(rel)
    result.deleted_files = len(deleted_paths)
    result.changed_files = len(changed_paths)
    result.new_files = len(new_paths)

    # Delete vectors for removed paths first; SQLite deletion is done in the transaction below.
    if deleted_paths:
        vs.delete_paths(deleted_paths)

    for rel in changed_paths:
        src = current_by_path[rel]
        chunk_result = chunk_source(src, config)
        chunks = chunk_result.chunks
        vectors = _vectors_for_chunks(config, db, embedder, chunks)
        with db.transaction() as conn:
            existing = db.get_file_by_path(conn, rel)
            file_id = db.upsert_file(
                conn,
                path=src.rel_path,
                size=src.size,
                mtime_ns=src.mtime_ns,
                content_hash=src.content_hash,
                language=detect_language(src.rel_path),
                encoding=src.encoding,
                git_commit=git_commit,
            )
            if existing is not None:
                db.delete_chunks_for_file(conn, file_id)
                conn.execute("DELETE FROM symbols WHERE file_id=?", (file_id,))
                conn.execute("DELETE FROM edges WHERE src_file_id=?", (file_id,))
            for ch, vec in zip(chunks, vectors):
                db.put_embedding_cache(conn, ch.content_hash, config.model_key, vec)
            db.insert_chunks(conn, file_id, chunks)
            db.insert_symbols(conn, file_id, chunk_result.symbols)
            db.insert_edges(conn, file_id, chunk_result.edges)
            db.set_meta(conn, "last_sync_at", str(time.time()))
            db.set_meta(conn, "embedding_dim", str(len(vectors[0]) if vectors else embedder.dimension()))
        vs.add_or_replace(chunks, vectors)
        result.indexed_files += 1
        result.chunks += len(chunks)
        result.symbols += len(chunk_result.symbols)
        result.edges += len(chunk_result.edges)

    if deleted_paths:
        with db.transaction() as conn:
            for rel in deleted_paths:
                db.mark_file_deleted(conn, rel)
            db.set_meta(conn, "last_sync_at", str(time.time()))
    return result


def _vectors_for_chunks(config: AppConfig, db: MetadataDb, embedder: EmbeddingProvider, chunks: list[Chunk]) -> list[list[float]]:
    vectors: list[list[float] | None] = [None] * len(chunks)
    missing_indices: list[int] = []
    with db.connect() as conn:
        for i, ch in enumerate(chunks):
            cached = db.cached_embedding(conn, ch.content_hash, config.model_key)
            if cached is not None:
                vectors[i] = cached
            else:
                missing_indices.append(i)
    if missing_indices:
        texts = [_embedding_text(chunks[i]) for i in missing_indices]
        new_vectors = embedder.encode(texts)
        for i, vec in zip(missing_indices, new_vectors):
            vectors[i] = vec
    return [v if v is not None else [] for v in vectors]


def _embedding_text(ch: Chunk) -> str:
    parts = [f"path: {ch.file_path}"]
    if ch.heading_path:
        parts.append(f"heading: {ch.heading_path}")
    if ch.symbol_name:
        parts.append(f"symbol: {ch.symbol_name} ({ch.symbol_kind})")
    parts.append(ch.content)
    return "\n".join(parts)


def _git_commit(root: Path) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, timeout=3)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        return None
    return None


def _remove_db(config: AppConfig) -> None:
    import shutil
    if config.db.exists():
        shutil.rmtree(config.db)
