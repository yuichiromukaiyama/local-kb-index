from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from .chunkers import Chunk, Edge, Symbol
from .config import AppConfig, CHUNKER_VERSION, SCHEMA_VERSION
from .errors import KbError
from .embedding import pack_vector, unpack_vector


class MetadataDb:
    def __init__(self, config: AppConfig):
        self.config = config
        self.path = config.sqlite_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self.set_meta(conn, "schema_version", str(SCHEMA_VERSION))
            self.set_meta(conn, "chunker_version", str(CHUNKER_VERSION))
            self.set_meta(conn, "embedding_model", self.config.embedding.model)
            self.set_meta(conn, "embedding_model_key", self.config.model_key)
            self.set_meta(conn, "created_or_updated_at", str(time.time()))
            conn.commit()

    def check_schema(self, allow_missing: bool = False) -> None:
        if not self.path.exists():
            if allow_missing:
                return
            raise KbError("KB001", f"missing sqlite db: {self.path}")
        with self.connect() as conn:
            try:
                v = self.get_meta(conn, "schema_version")
            except sqlite3.Error as exc:
                raise KbError("KB008", f"failed to read metadata: {exc}", cause=exc) from exc
            if v is None:
                raise KbError("KB002", "schema_version is missing")
            if int(v) != SCHEMA_VERSION:
                raise KbError("KB002", f"expected {SCHEMA_VERSION}, got {v}")

    @staticmethod
    def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    @staticmethod
    def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            "INSERT INTO meta(key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, time.time()),
        )

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_file_by_path(self, conn: sqlite3.Connection, rel_path: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM files WHERE path=?", (rel_path,)).fetchone()

    def upsert_file(self, conn: sqlite3.Connection, *, path: str, size: int, mtime_ns: int, content_hash: str, language: str, encoding: str, git_commit: str | None = None) -> int:
        now = time.time()
        conn.execute(
            """
            INSERT INTO files(path, size, mtime_ns, content_hash, language, encoding, git_commit, indexed_at, deleted_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            ON CONFLICT(path) DO UPDATE SET
              size=excluded.size, mtime_ns=excluded.mtime_ns, content_hash=excluded.content_hash,
              language=excluded.language, encoding=excluded.encoding, git_commit=excluded.git_commit,
              indexed_at=excluded.indexed_at, deleted_at=NULL, updated_at=excluded.updated_at
            """,
            (path, size, mtime_ns, content_hash, language, encoding, git_commit, now, now),
        )
        row = conn.execute("SELECT id FROM files WHERE path=?", (path,)).fetchone()
        return int(row["id"])

    def mark_file_deleted(self, conn: sqlite3.Connection, rel_path: str) -> None:
        now = time.time()
        row = self.get_file_by_path(conn, rel_path)
        if row is None:
            return
        file_id = int(row["id"])
        conn.execute("UPDATE files SET deleted_at=?, updated_at=? WHERE id=?", (now, now, file_id))
        self.delete_chunks_for_file(conn, file_id)
        conn.execute("DELETE FROM symbols WHERE file_id=?", (file_id,))
        conn.execute("DELETE FROM edges WHERE src_file_id=?", (file_id,))

    def delete_chunks_for_file(self, conn: sqlite3.Connection, file_id: int) -> None:
        ids = [r["id"] for r in conn.execute("SELECT id FROM chunks WHERE file_id=?", (file_id,)).fetchall()]
        if ids:
            conn.executemany("DELETE FROM chunks_fts WHERE rowid=?", [(i,) for i in ids])
        conn.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))

    def insert_chunks(self, conn: sqlite3.Connection, file_id: int, chunks: list[Chunk]) -> None:
        now = time.time()
        for ch in chunks:
            conn.execute(
                """
                INSERT INTO chunks(chunk_id, file_id, path, language, symbol_name, symbol_kind, heading_path,
                  start_line, end_line, content, parent_context, imports_json, exports_json, token_count,
                  content_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ch.chunk_id, file_id, ch.file_path, ch.language, ch.symbol_name, ch.symbol_kind,
                    ch.heading_path, ch.start_line, ch.end_line, ch.content, ch.parent_context,
                    json.dumps(ch.imports, ensure_ascii=False), json.dumps(ch.exports, ensure_ascii=False),
                    ch.token_count, ch.content_hash, now, now,
                ),
            )
            chunk_pk = int(conn.execute("SELECT id FROM chunks WHERE chunk_id=?", (ch.chunk_id,)).fetchone()["id"])
            conn.execute(
                "INSERT INTO chunks_fts(rowid, content, path, symbol_name, heading_path) VALUES (?, ?, ?, ?, ?)",
                (chunk_pk, ch.content, ch.file_path, ch.symbol_name or "", ch.heading_path or ""),
            )

    def insert_symbols(self, conn: sqlite3.Connection, file_id: int, symbols: list[Symbol]) -> None:
        now = time.time()
        for s in symbols:
            conn.execute(
                "INSERT INTO symbols(file_id, path, name, kind, start_line, end_line, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (file_id, s.path, s.name, s.kind, s.start_line, s.end_line, now),
            )

    def insert_edges(self, conn: sqlite3.Connection, file_id: int, edges: list[Edge]) -> None:
        now = time.time()
        for e in edges:
            conn.execute(
                "INSERT INTO edges(src_file_id, src_path, dst, edge_type, evidence, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (file_id, e.src_path, e.dst, e.edge_type, e.evidence, now),
            )

    def cached_embedding(self, conn: sqlite3.Connection, chunk_hash: str, model_key: str) -> list[float] | None:
        row = conn.execute(
            "SELECT vector_blob, dim FROM embedding_cache WHERE chunk_hash=? AND model_key=?",
            (chunk_hash, model_key),
        ).fetchone()
        if not row:
            return None
        vec = unpack_vector(row["vector_blob"])
        return vec if len(vec) == int(row["dim"]) else None

    def put_embedding_cache(self, conn: sqlite3.Connection, chunk_hash: str, model_key: str, vector: list[float]) -> None:
        conn.execute(
            """
            INSERT INTO embedding_cache(chunk_hash, model_key, dim, vector_blob, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chunk_hash, model_key) DO UPDATE SET dim=excluded.dim, vector_blob=excluded.vector_blob
            """,
            (chunk_hash, model_key, len(vector), pack_vector(vector), time.time()),
        )

    def chunks_for_paths(self, conn: sqlite3.Connection, paths: list[str]) -> list[sqlite3.Row]:
        if not paths:
            return []
        qs = ",".join("?" for _ in paths)
        return conn.execute(f"SELECT * FROM chunks WHERE path IN ({qs})", paths).fetchall()

    def all_indexed_paths(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute("SELECT path FROM files WHERE deleted_at IS NULL").fetchall()
        return {str(r["path"]) for r in rows}

    def file_summary(self, conn: sqlite3.Connection) -> dict[str, int]:
        return {
            "files": int(conn.execute("SELECT count(*) c FROM files WHERE deleted_at IS NULL").fetchone()["c"]),
            "deleted_files": int(conn.execute("SELECT count(*) c FROM files WHERE deleted_at IS NOT NULL").fetchone()["c"]),
            "chunks": int(conn.execute("SELECT count(*) c FROM chunks").fetchone()["c"]),
            "symbols": int(conn.execute("SELECT count(*) c FROM symbols").fetchone()["c"]),
            "edges": int(conn.execute("SELECT count(*) c FROM edges").fetchone()["c"]),
        }


SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  size INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  language TEXT NOT NULL,
  encoding TEXT NOT NULL,
  git_commit TEXT,
  indexed_at REAL,
  deleted_at REAL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_files_deleted ON files(deleted_at);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chunk_id TEXT NOT NULL UNIQUE,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  language TEXT NOT NULL,
  symbol_name TEXT,
  symbol_kind TEXT,
  heading_path TEXT,
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  content TEXT NOT NULL,
  parent_context TEXT,
  imports_json TEXT NOT NULL DEFAULT '[]',
  exports_json TEXT NOT NULL DEFAULT '[]',
  token_count INTEGER NOT NULL DEFAULT 0,
  content_hash TEXT NOT NULL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
CREATE INDEX IF NOT EXISTS idx_chunks_symbol ON chunks(symbol_name);
CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(content_hash);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  content,
  path UNINDEXED,
  symbol_name UNINDEXED,
  heading_path UNINDEXED,
  tokenize = 'unicode61 tokenchars ''_-.'''
);

CREATE TABLE IF NOT EXISTS symbols (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_path ON symbols(path);

CREATE TABLE IF NOT EXISTS edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  src_file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  src_path TEXT NOT NULL,
  dst TEXT NOT NULL,
  edge_type TEXT NOT NULL,
  evidence TEXT,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_path);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);

CREATE TABLE IF NOT EXISTS embedding_cache (
  chunk_hash TEXT NOT NULL,
  model_key TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector_blob BLOB NOT NULL,
  created_at REAL NOT NULL,
  PRIMARY KEY(chunk_hash, model_key)
);

CREATE TABLE IF NOT EXISTS query_cache (
  query_hash TEXT PRIMARY KEY,
  query TEXT NOT NULL,
  mode TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  command TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at REAL NOT NULL,
  finished_at REAL,
  detail_json TEXT NOT NULL DEFAULT '{}'
);
"""
