from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

from .config import AppConfig, SCHEMA_VERSION
from .db import MetadataDb
from .vector_store import VectorStore


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    remediation: str = ""


@dataclass
class DoctorResult:
    ok: bool
    checks: list[Check] = field(default_factory=list)
    system: dict[str, Any] = field(default_factory=dict)


def doctor(config: AppConfig, *, offline_check: bool = False) -> DoctorResult:
    checks: list[Check] = []
    checks.append(Check("root exists", config.root.exists(), str(config.root), "Pass --root correctly."))
    checks.append(Check("db directory", config.db.exists(), str(config.db), "Run kb index."))
    checks.append(Check("sqlite db", config.sqlite_path.exists(), str(config.sqlite_path), "Run kb index."))
    checks.extend(_dependency_checks())
    checks.append(_code_command_check())
    checks.append(_extension_check())
    if config.sqlite_path.exists():
        checks.extend(_schema_checks(config))
        checks.extend(_vector_checks(config))
    if offline_check:
        checks.append(_offline_model_check(config))
    ok = all(c.ok for c in checks if c.name not in {"VS Code extension installed"})
    return DoctorResult(
        ok=ok,
        checks=checks,
        system={
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "kb_schema_version": SCHEMA_VERSION,
            "root": str(config.root),
            "db": str(config.db),
            "model": config.embedding.model,
            "local_files_only": config.embedding.local_files_only,
        },
    )


def _dependency_checks() -> list[Check]:
    deps = ["numpy", "yaml", "lancedb", "pyarrow", "sentence_transformers", "rich"]
    return [Check(f"python package: {d}", importlib.util.find_spec(d) is not None, d, f"pip install {d.replace('_', '-')}") for d in deps]


def _schema_checks(config: AppConfig) -> list[Check]:
    checks: list[Check] = []
    db = MetadataDb(config)
    try:
        db.check_schema()
        checks.append(Check("schema version", True, f"{SCHEMA_VERSION}"))
        with db.connect() as conn:
            dim = db.get_meta(conn, "embedding_dim")
            model = db.get_meta(conn, "embedding_model")
            checks.append(Check("embedding model metadata", bool(model), str(model), "Run kb rebuild."))
            checks.append(Check("embedding dimension metadata", bool(dim), str(dim), "Run kb rebuild."))
            try:
                conn.execute("SELECT count(*) FROM chunks_fts").fetchone()
                checks.append(Check("FTS5 table", True, "chunks_fts"))
            except Exception as exc:
                checks.append(Check("FTS5 table", False, str(exc), "Run kb rebuild."))
    except Exception as exc:
        checks.append(Check("schema version", False, str(exc), "Run kb rebuild."))
    return checks


def _vector_checks(config: AppConfig) -> list[Check]:
    try:
        vs = VectorStore(config)
        checks = [Check("LanceDB vector table", vs.count() >= 0, f"rows={vs.count()}", "Run kb rebuild.")]
        checks.append(Check("LanceDB vector column", vs.vector_column_ok(), "vector", "Run kb rebuild."))
        return checks
    except Exception as exc:
        return [Check("LanceDB vector table", False, str(exc), "Run kb rebuild.")]


def _code_command_check() -> Check:
    code = shutil.which("code")
    return Check("VS Code code command", code is not None, code or "not found", "Install VS Code shell command: Shell Command: Install 'code' command in PATH.")


def _extension_check() -> Check:
    code = shutil.which("code")
    if not code:
        return Check("VS Code extension installed", False, "code command not found", "Install code command first.")
    try:
        out = subprocess.run([code, "--list-extensions"], capture_output=True, text=True, timeout=10)
        installed = "local.local-kb-vscode-extension" in out.stdout.splitlines()
        return Check("VS Code extension installed", installed, "local.local-kb-vscode-extension", "Install vscode-extension/local-kb-vscode-extension-*.vsix")
    except Exception as exc:
        return Check("VS Code extension installed", False, str(exc), "Check VS Code CLI.")


def _offline_model_check(config: AppConfig) -> Check:
    try:
        from sentence_transformers import SentenceTransformer
        SentenceTransformer(config.embedding.model, local_files_only=True, revision=config.embedding.revision)
        return Check("offline embedding model", True, config.embedding.model)
    except Exception as exc:
        return Check("offline embedding model", False, str(exc), "Download/pin the model internally or set local_files_only=false temporarily.")
