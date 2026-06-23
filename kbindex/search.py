from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
from typing import Any

from .config import AppConfig
from .db import MetadataDb
from .embedding import EmbeddingProvider
from .vector_store import VectorStore


@dataclass
class SearchResult:
    rank: int
    path: str
    start_line: int
    end_line: int
    score: float
    mode_scores: dict[str, float] = field(default_factory=dict)
    symbol_name: str | None = None
    symbol_kind: str | None = None
    heading_path: str | None = None
    language: str | None = None
    reason: str | None = None
    snippet: str = ""


@dataclass(frozen=True)
class PathFilter:
    """Repository-relative include/exclude glob filter for query results.

    Patterns are intentionally evaluated against normalized repository-relative paths
    stored in the index. Examples:

      --path src              matches src/... and src exactly
      --include docs/**       matches everything under docs
      --include **/*.md       matches Markdown files anywhere
      --exclude **/tests/**   excludes test directories

    `--path` is a CLI alias for include patterns.
    """

    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    @classmethod
    def from_patterns(
        cls,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> "PathFilter":
        return cls(
            include=tuple(_normalize_path_pattern(p) for p in (include or []) if str(p).strip()),
            exclude=tuple(_normalize_path_pattern(p) for p in (exclude or []) if str(p).strip()),
        )

    @property
    def active(self) -> bool:
        return bool(self.include or self.exclude)

    def matches(self, path: str) -> bool:
        normalized = _normalize_index_path(path)
        if self.include and not any(_path_pattern_matches(normalized, pattern) for pattern in self.include):
            return False
        if self.exclude and any(_path_pattern_matches(normalized, pattern) for pattern in self.exclude):
            return False
        return True


def _normalize_index_path(path: str) -> str:
    path = str(path or "").replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path.lstrip("/").rstrip("/")


def _normalize_path_pattern(pattern: str) -> str:
    pattern = _normalize_index_path(pattern)
    if pattern.endswith("/"):
        pattern = pattern.rstrip("/") + "/**"
    return pattern


def _has_glob(pattern: str) -> bool:
    return any(ch in pattern for ch in "*?[")


def _path_pattern_matches(path: str, pattern: str) -> bool:
    if not pattern:
        return True
    if _has_glob(pattern):
        if fnmatch.fnmatchcase(path, pattern):
            return True
        # Treat a directory-style glob like `src/**` as also matching `src`.
        if pattern.endswith("/**") and path == pattern[:-3].rstrip("/"):
            return True
        return False

    # Non-glob patterns are interpreted as an exact file path or a directory prefix.
    base = pattern.rstrip("/")
    return path == base or path.startswith(base + "/")


def query(
    config: AppConfig,
    text: str,
    *,
    mode: str | None = None,
    limit: int | None = None,
    format_for_copilot: bool = False,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
) -> list[SearchResult]:
    """Search using vector retrieval only.

    Legacy modes such as hybrid/fts/exact/symbol are intentionally ignored and mapped
    to vector so that existing config files or older VS Code settings do not produce
    noisy warnings or hard failures.
    """
    _normalize_mode(mode or config.search.default_mode)
    limit = limit or config.search.top_k
    path_filter = PathFilter.from_patterns(include_paths, exclude_paths)
    db = MetadataDb(config)
    db.check_schema()

    expanded = expand_query(config, text)
    candidates: dict[str, SearchResult] = {}
    for result in _vector_results(config, expanded, config.search.candidate_k, path_filter=path_filter):
        if not path_filter.matches(result.path):
            continue
        key = f"{result.path}:{result.start_line}:{result.end_line}"
        current = candidates.get(key)
        if current is None or result.score > current.score:
            candidates[key] = result
        candidates[key].mode_scores["vector"] = max(
            candidates[key].mode_scores.get("vector", 0.0),
            result.score,
        )

    scored = _score_vector_only(config, list(candidates.values()))
    for i, result in enumerate(scored[:limit], start=1):
        result.rank = i
        if format_for_copilot:
            result.reason = _reason(result)
    return scored[:limit]


def _normalize_mode(mode: str | None) -> str:
    # Keep this function explicit for future validation. Today every legacy/non-vector
    # mode is coerced to vector to avoid breaking existing .kb/config.yml files.
    return "vector"


def expand_query(config: AppConfig, text: str) -> list[str]:
    queries = [text]
    if not config.search.query_expansion:
        return queries
    low = text.lower()
    for term, expansions in config.search.glossary.items():
        if term.lower() in low or any(e.lower() in low for e in expansions):
            for expansion in expansions:
                if expansion not in queries:
                    queries.append(expansion)
            if term not in queries:
                queries.append(term)
    return queries[:8]


def _vector_results(
    config: AppConfig,
    queries: list[str],
    candidate_k: int,
    *,
    path_filter: "PathFilter",
) -> list[SearchResult]:
    embedder = EmbeddingProvider(config)
    vector_store = VectorStore(config)

    # Correctness is preferred over returning accidentally incomplete results.
    # If a path filter is active, retrieve the full ranked vector list and apply the
    # include/exclude filter locally. This guarantees that narrow directories are not
    # missed because they fell outside the default candidate_k window.
    # The unfiltered path remains fast and uses candidate_k as before.
    search_limit = candidate_k
    if path_filter.active:
        search_limit = max(candidate_k, vector_store.count())

    out: list[SearchResult] = []
    for query_text in queries:
        query_vector = embedder.encode([query_text])[0]
        rows = vector_store.vector_search(query_vector, search_limit)
        out.extend(_rows_to_results(rows))
    return out


def _rows_to_results(rows: list[dict[str, Any]]) -> list[SearchResult]:
    out: list[SearchResult] = []
    for row in rows:
        raw_distance = float(row.get("_distance", 0.0) or 0.0)
        score = 1.0 / (1.0 + raw_distance)
        out.append(SearchResult(
            rank=0,
            path=str(row.get("path", "")),
            start_line=int(row.get("start_line", 1) or 1),
            end_line=int(row.get("end_line", 1) or 1),
            score=score,
            symbol_name=str(row.get("symbol_name") or "") or None,
            heading_path=str(row.get("heading_path") or "") or None,
            language=str(row.get("language") or "") or None,
            snippet=str(row.get("content") or ""),
        ))
    return out


def _score_vector_only(config: AppConfig, results: list[SearchResult]) -> list[SearchResult]:
    # Vector distance is the only ranking signal. Metadata remains in the response for
    # explainability, but it no longer boosts or downranks results.
    for result in results:
        if result.mode_scores:
            result.score = result.mode_scores.get("vector", result.score)
        result.snippet = _trim_snippet(result.snippet, config.search.snippet_chars)
    results.sort(key=lambda item: item.score, reverse=True)

    deduped: list[SearchResult] = []
    seen: set[tuple[str, int, int]] = set()
    for result in results:
        key = (result.path, result.start_line, result.end_line)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _trim_snippet(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def _reason(result: SearchResult) -> str:
    parts = ["matched by local vector search"]
    if result.symbol_name:
        parts.append(f"symbol={result.symbol_name}")
    if result.heading_path:
        parts.append(f"heading={result.heading_path}")
    return "; ".join(parts)


def results_to_json(
    query_text: str,
    results: list[SearchResult],
    *,
    compact: bool = False,
    content: str = "snippet",
    max_snippet_chars: int | None = None,
) -> dict[str, Any]:
    """Serialize search results.

    The default shape is verbose and stable for humans/debugging.
    compact=True returns a token-efficient shape for AI/Copilot tool output:

      {"q":"...","r":[{"p":"file","l":"1-10","sc":0.812,"s":"symbol","t":"snippet"}]}

    Null/empty fields are omitted. Result rank is represented by array order.
    """
    normalized_content = content if content in {"snippet", "none"} else "snippet"
    if compact:
        compact_results: list[dict[str, Any]] = []
        for result in results:
            item: dict[str, Any] = {
                "p": result.path,
                "l": f"{result.start_line}-{result.end_line}",
                "sc": round(float(result.score), 4),
            }
            symbol = result.symbol_name or result.heading_path
            if symbol:
                item["s"] = symbol
            if normalized_content == "snippet":
                snippet = _compact_snippet(result.snippet, max_snippet_chars)
                if snippet:
                    item["t"] = snippet
            compact_results.append(item)
        return {"q": query_text, "r": compact_results}

    return {
        "query": query_text,
        "mode": "vector",
        "results": [
            _full_result_to_dict(result, normalized_content, max_snippet_chars)
            for result in results
        ],
    }


def _full_result_to_dict(
    result: SearchResult,
    content: str,
    max_snippet_chars: int | None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "rank": result.rank,
        "path": result.path,
        "start_line": result.start_line,
        "end_line": result.end_line,
        "score": result.score,
        "symbol_name": result.symbol_name,
        "symbol_kind": result.symbol_kind,
        "heading_path": result.heading_path,
        "language": result.language,
        "reason": result.reason,
    }
    if content == "snippet":
        item["snippet"] = _compact_snippet(result.snippet, max_snippet_chars)
    return item


def _compact_snippet(text: str, limit: int | None) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    if limit is None or limit <= 0 or len(text) <= limit:
        return text
    return text[:limit].rstrip() + " ..."
