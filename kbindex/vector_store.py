from __future__ import annotations

from pathlib import Path
from typing import Any

from .chunkers import Chunk
from .config import AppConfig
from .errors import KbError

TABLE_NAME = "chunks"


class VectorStore:
    def __init__(self, config: AppConfig):
        self.config = config
        try:
            import lancedb  # type: ignore
            import pyarrow as pa  # type: ignore
        except Exception as exc:
            raise KbError("KB014", "lancedb and pyarrow are required for vector storage", cause=exc) from exc
        self.lancedb = lancedb
        self.pa = pa
        config.lance_dir.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(config.lance_dir))

    def ensure_table(self, vector_dim: int) -> None:
        names = set(self.db.table_names())
        if TABLE_NAME in names:
            # Open once to validate vector column.
            table = self.db.open_table(TABLE_NAME)
            schema = table.schema
            if "vector" not in schema.names:
                raise KbError("KB003", "LanceDB table exists but vector column is missing")
            return
        schema = self.pa.schema([
            self.pa.field("chunk_id", self.pa.string()),
            self.pa.field("path", self.pa.string()),
            self.pa.field("start_line", self.pa.int64()),
            self.pa.field("end_line", self.pa.int64()),
            self.pa.field("content", self.pa.string()),
            self.pa.field("language", self.pa.string()),
            self.pa.field("symbol_name", self.pa.string()),
            self.pa.field("heading_path", self.pa.string()),
            self.pa.field("content_hash", self.pa.string()),
            self.pa.field("vector", self.pa.list_(self.pa.float32(), vector_dim)),
        ])
        self.db.create_table(TABLE_NAME, data=[], schema=schema)

    def drop_table(self) -> None:
        if TABLE_NAME in set(self.db.table_names()):
            self.db.drop_table(TABLE_NAME)

    def add_or_replace(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")
        if not chunks:
            return
        table = self.db.open_table(TABLE_NAME)
        ids = [ch.chunk_id for ch in chunks]
        self.delete_chunk_ids(ids)
        rows = []
        for ch, vec in zip(chunks, vectors):
            rows.append({
                "chunk_id": ch.chunk_id,
                "path": ch.file_path,
                "start_line": ch.start_line,
                "end_line": ch.end_line,
                "content": ch.content,
                "language": ch.language,
                "symbol_name": ch.symbol_name or "",
                "heading_path": ch.heading_path or "",
                "content_hash": ch.content_hash,
                "vector": [float(x) for x in vec],
            })
        table.add(rows)

    def delete_chunk_ids(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        if TABLE_NAME not in set(self.db.table_names()):
            return
        table = self.db.open_table(TABLE_NAME)
        for cid in chunk_ids:
            safe = cid.replace("'", "''")
            try:
                table.delete(f"chunk_id = '{safe}'")
            except Exception:
                # Continue; stale vectors are filtered by SQLite metadata at query time.
                pass

    def delete_paths(self, paths: list[str]) -> None:
        if not paths or TABLE_NAME not in set(self.db.table_names()):
            return
        table = self.db.open_table(TABLE_NAME)
        for path in paths:
            safe = path.replace("'", "''")
            try:
                table.delete(f"path = '{safe}'")
            except Exception:
                pass

    def vector_search(self, query_vector: list[float], limit: int) -> list[dict[str, Any]]:
        try:
            table = self.db.open_table(TABLE_NAME)
            return table.search(query_vector, vector_column_name="vector").limit(limit).to_list()
        except ValueError as exc:
            if "vector column" in str(exc):
                raise KbError("KB003", str(exc), cause=exc) from exc
            raise KbError("KB009", str(exc), cause=exc) from exc
        except Exception as exc:
            raise KbError("KB009", str(exc), cause=exc) from exc

    def count(self) -> int:
        if TABLE_NAME not in set(self.db.table_names()):
            return 0
        table = self.db.open_table(TABLE_NAME)
        try:
            return int(table.count_rows())
        except Exception:
            return len(table.to_list())

    def vector_column_ok(self) -> bool:
        if TABLE_NAME not in set(self.db.table_names()):
            return False
        table = self.db.open_table(TABLE_NAME)
        return "vector" in table.schema.names
