from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_config
from .indexer import sync
from .search import query, results_to_json
from .status import status


def create_app(root: str = ".", db: str | None = None):
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
    except Exception as exc:
        raise RuntimeError("fastapi and pydantic are required for kb serve") from exc

    cfg = load_config(root, db)
    app = FastAPI(title="Local KB", version="1.0.0")

    class QueryRequest(BaseModel):
        query: str
        # Kept for backward compatibility with older clients. Ignored; vector search is always used.
        mode: str | None = None
        limit: int | None = None
        compact: bool = True
        content: str = "snippet"
        max_snippet_chars: int | None = 600
        # Repository-relative path filters. `path` is an alias for include filters.
        path: str | list[str] | None = None
        include: list[str] | None = None
        exclude: list[str] | None = None

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "root": str(cfg.root), "db": str(cfg.db)}

    @app.get("/status")
    def status_endpoint() -> dict[str, Any]:
        return status(cfg).__dict__

    @app.post("/query")
    def query_endpoint(req: QueryRequest) -> dict[str, Any]:
        try:
            include_paths = _as_list(req.include) + _as_list(req.path)
            exclude_paths = _as_list(req.exclude)
            res = query(
                cfg,
                req.query,
                mode="vector",
                limit=req.limit,
                format_for_copilot=req.compact,
                include_paths=include_paths,
                exclude_paths=exclude_paths,
            )
            return results_to_json(
                req.query,
                res,
                compact=req.compact,
                content=req.content,
                max_snippet_chars=req.max_snippet_chars,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/sync")
    def sync_endpoint() -> dict[str, Any]:
        # This endpoint exists for explicit local use; the VS Code LM tool intentionally calls query only.
        return sync(cfg).__dict__

    return app


def _as_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(item) for item in value if str(item).strip()]


def run_server(root: str, db: str | None, host: str, port: int) -> None:
    import uvicorn
    app = create_app(root, db)
    uvicorn.run(app, host=host, port=port)
