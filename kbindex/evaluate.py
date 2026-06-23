from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import AppConfig
from .search import query


@dataclass
class EvalCaseResult:
    query: str
    expected: list[str]
    found: list[str]
    recall_at_k: float
    mrr: float
    hit: bool


@dataclass
class EvalResult:
    cases: list[EvalCaseResult] = field(default_factory=list)
    recall_at_k: float = 0.0
    mrr: float = 0.0
    hit_rate: float = 0.0


def run_eval(config: AppConfig, eval_file: Path, *, k: int | None = None) -> EvalResult:
    raw = yaml.safe_load(eval_file.read_text(encoding="utf-8")) or {}
    cases = raw.get("queries", [])
    results: list[EvalCaseResult] = []
    k = k or config.search.top_k
    for case in cases:
        q = str(case.get("query", ""))
        expected = [str(x) for x in case.get("expected", [])]
        res = query(config, q, mode=case.get("mode") or config.search.default_mode, limit=k)
        found = [r.path for r in res]
        hit_positions = [i + 1 for i, p in enumerate(found) if any(exp in p for exp in expected)]
        hit = bool(hit_positions)
        recall = 1.0 if hit else 0.0
        mrr = 1.0 / hit_positions[0] if hit_positions else 0.0
        results.append(EvalCaseResult(q, expected, found, recall, mrr, hit))
    n = max(len(results), 1)
    return EvalResult(
        cases=results,
        recall_at_k=sum(c.recall_at_k for c in results) / n,
        mrr=sum(c.mrr for c in results) / n,
        hit_rate=sum(1 for c in results if c.hit) / n,
    )
