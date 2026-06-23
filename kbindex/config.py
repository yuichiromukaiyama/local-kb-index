from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import KbError

SCHEMA_VERSION = 3
CHUNKER_VERSION = 3
DEFAULT_DB_DIR = ".kb_index"
DEFAULT_CONFIG_DIR = ".kb"
DEFAULT_CONFIG_FILE = "config.yml"
DEFAULT_IGNORE_FILE = ".kbignore"


@dataclass
class IndexConfig:
    include: list[str] = field(default_factory=lambda: [
        "**/*.md", "**/*.mdx", "**/*.txt", "**/*.py", "**/*.ts", "**/*.tsx",
        "**/*.js", "**/*.jsx", "**/*.json", "**/*.jsonc", "**/*.yaml", "**/*.yml",
        "**/*.tf", "**/*.sql", "**/*.toml", "**/*.ini", "**/*.sh", "**/*.bash",
        "**/*.zsh", "**/*.dockerfile", "Dockerfile", "**/Dockerfile",
    ])
    exclude: list[str] = field(default_factory=lambda: [
        ".git/**", ".kb_index/**", ".kb/**/cache/**", "node_modules/**", ".venv/**",
        "venv/**", "dist/**", "build/**", "coverage/**", ".next/**", ".turbo/**",
        "target/**", "__pycache__/**", "*.pyc", "*.pyo", "*.lock", "package-lock.json",
        "yarn.lock", "pnpm-lock.yaml", "*.min.js", "*.map", "*.png", "*.jpg", "*.jpeg",
        "*.gif", "*.webp", "*.pdf", "*.zip", "*.tar", "*.gz", "*.7z", "*.sqlite",
        "*.db", "*.pem", "*.key", "*.p12", "*.pfx", ".env", ".env.*",
    ])
    max_file_bytes: int = 1_000_000
    hidden_files: bool = False
    follow_symlinks: bool = False
    large_repo_file_warning: int = 20_000


@dataclass
class ChunkingConfig:
    max_chars: int = 1800
    overlap_chars: int = 250
    strategy: str = "language-aware"
    parent_context_chars: int = 1200
    min_chunk_chars: int = 80
    use_tree_sitter: bool = True


@dataclass
class EmbeddingConfig:
    provider: str = "sentence-transformers"
    model: str = "BAAI/bge-m3"
    revision: str | None = None
    local_files_only: bool = False
    batch_size: int = 32
    normalize: bool = True
    device: str | None = None


@dataclass
class SearchConfig:
    default_mode: str = "vector"
    top_k: int = 8
    candidate_k: int = 50
    rerank: bool = False
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    query_expansion: bool = False
    snippet_chars: int = 1200
    # Retained for backward-compatible config loading. Vector-only search ignores these.
    rrf_k: int = 60
    boost_path: bool = False
    boost_symbol: bool = False
    boost_recency: bool = False
    downrank_tests: bool = False
    glossary: dict[str, list[str]] = field(default_factory=lambda: {
        "署名付きURL": ["signed URL", "SAS", "Shared Access Signature", "presigned URL"],
        "権限": ["permission", "authorization", "access control", "ACL"],
        "認証": ["authentication", "auth", "login", "identity"],
        "認可": ["authorization", "permission", "policy", "access control"],
        "アップロード": ["upload", "put blob", "create file", "upload session"],
        "削除": ["delete", "remove", "trash", "prune"],
        "検索": ["search", "query", "retrieval", "index"],
    })


@dataclass
class SecurityConfig:
    secret_scan: bool = True
    block_secret_files: bool = True
    allow_secrets: bool = False
    redact_logs: bool = True
    allow_hidden_files: bool = False
    blocked_file_patterns: list[str] = field(default_factory=lambda: [
        ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa", "id_ed25519",
        "**/secrets.*", "**/credentials.*",
    ])


@dataclass
class RuntimeConfig:
    log_level: str = "info"
    lock_timeout_seconds: int = 120
    stale_lock_seconds: int = 7200
    query_cache_ttl_seconds: int = 3600
    watch_debounce_seconds: float = 5.0
    watch_batch_interval_seconds: float = 30.0
    max_workers: int = max(2, (os.cpu_count() or 4) // 2)


@dataclass
class AppConfig:
    root: Path
    db: Path
    config_path: Path
    schema_version: int = SCHEMA_VERSION
    chunker_version: int = CHUNKER_VERSION
    index: IndexConfig = field(default_factory=IndexConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    @property
    def sqlite_path(self) -> Path:
        return self.db / "kb.sqlite"

    @property
    def lance_dir(self) -> Path:
        return self.db / "lancedb"

    @property
    def logs_dir(self) -> Path:
        return self.db / "logs"

    @property
    def lock_path(self) -> Path:
        return self.db / "index.lock"

    @property
    def ignore_path(self) -> Path:
        return self.root / DEFAULT_IGNORE_FILE

    @property
    def model_key(self) -> str:
        rev = self.embedding.revision or "default"
        return f"{self.embedding.provider}:{self.embedding.model}:{rev}:normalize={self.embedding.normalize}"


def _merge_dataclass(instance: Any, data: dict[str, Any]) -> Any:
    if not isinstance(data, dict):
        return instance
    for key, value in data.items():
        if hasattr(instance, key):
            current = getattr(instance, key)
            if hasattr(current, "__dataclass_fields__") and isinstance(value, dict):
                _merge_dataclass(current, value)
            else:
                setattr(instance, key, value)
    return instance


def default_config_dict() -> dict[str, Any]:
    cfg = AppConfig(root=Path("."), db=Path(DEFAULT_DB_DIR), config_path=Path(DEFAULT_CONFIG_DIR) / DEFAULT_CONFIG_FILE)
    return {
        "index": cfg.index.__dict__,
        "chunking": cfg.chunking.__dict__,
        "embedding": cfg.embedding.__dict__,
        "search": cfg.search.__dict__,
        "security": cfg.security.__dict__,
        "runtime": cfg.runtime.__dict__,
    }


def load_config(root: str | Path = ".", db: str | Path | None = None, config_file: str | Path | None = None) -> AppConfig:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise KbError("KB006", f"root does not exist: {root_path}")
    db_path = Path(db).expanduser() if db is not None else root_path / DEFAULT_DB_DIR
    if not db_path.is_absolute():
        db_path = (Path.cwd() / db_path).resolve()
    else:
        db_path = db_path.resolve()
    config_path = Path(config_file).expanduser() if config_file else root_path / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()

    cfg = AppConfig(root=root_path, db=db_path, config_path=config_path)
    if config_path.exists():
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise KbError("KB013", f"failed to read config: {config_path}: {exc}", cause=exc) from exc
        _merge_dataclass(cfg, raw)
    # security setting must also reflect index.hidden_files for scanning.
    cfg.index.hidden_files = bool(cfg.index.hidden_files or cfg.security.allow_hidden_files)
    return cfg


def write_default_config(root: Path, overwrite: bool = False) -> Path:
    cfg_dir = root / DEFAULT_CONFIG_DIR
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / DEFAULT_CONFIG_FILE
    if cfg_file.exists() and not overwrite:
        return cfg_file
    cfg_file.write_text(yaml.safe_dump(default_config_dict(), sort_keys=False, allow_unicode=True), encoding="utf-8")
    return cfg_file


def write_default_ignore(root: Path, overwrite: bool = False) -> Path:
    ignore = root / DEFAULT_IGNORE_FILE
    if ignore.exists() and not overwrite:
        return ignore
    patterns = IndexConfig().exclude + SecurityConfig().blocked_file_patterns
    ignore.write_text("\n".join(patterns) + "\n", encoding="utf-8")
    return ignore
