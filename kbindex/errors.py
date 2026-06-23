from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorSpec:
    code: str
    exit_code: int
    title: str
    remediation: str


ERRORS: dict[str, ErrorSpec] = {
    "KB001": ErrorSpec("KB001", 3, "index not found", "Run: kb index --root . --db ./.kb_index"),
    "KB002": ErrorSpec("KB002", 4, "schema version mismatch", "Run: kb rebuild --root . --db ./.kb_index"),
    "KB003": ErrorSpec("KB003", 4, "vector column missing", "Run: kb rebuild --root . --db ./.kb_index"),
    "KB004": ErrorSpec("KB004", 5, "embedding model not available", "Install/download the configured embedding model, or set local_files_only=false temporarily."),
    "KB005": ErrorSpec("KB005", 7, "database is locked", "Wait for the running sync/index process or remove a stale lock after verification."),
    "KB006": ErrorSpec("KB006", 5, "workspace root not found", "Pass --root explicitly from an existing workspace directory."),
    "KB007": ErrorSpec("KB007", 5, "unsupported file encoding", "Exclude or convert the file to UTF-8 compatible text."),
    "KB008": ErrorSpec("KB008", 4, "corrupt index", "Run: kb rebuild --root . --db ./.kb_index --force"),
    "KB009": ErrorSpec("KB009", 1, "vector search failed", "Run: kb doctor. If the schema is invalid, rebuild the index."),
    "KB010": ErrorSpec("KB010", 4, "FTS index missing", "Run: kb rebuild --root . --db ./.kb_index"),
    "KB011": ErrorSpec("KB011", 6, "secret-like content blocked", "Exclude the file, or set security.allow_secrets=true only after review."),
    "KB012": ErrorSpec("KB012", 2, "index is stale", "Run: kb sync --root . --db ./.kb_index"),
    "KB013": ErrorSpec("KB013", 5, "invalid configuration", "Run: kb config --root . --show and fix .kb/config.yml."),
    "KB014": ErrorSpec("KB014", 5, "dependency missing", "Install the missing Python package or use the supported fallback."),
}


class KbError(RuntimeError):
    def __init__(self, code: str, detail: str = "", *, cause: Exception | None = None):
        self.code = code
        self.spec = ERRORS.get(code, ErrorSpec(code, 1, "unknown error", "Check logs and command arguments."))
        self.detail = detail
        self.cause = cause
        msg = f"{self.code}: {self.spec.title}"
        if detail:
            msg += f"\n{detail}"
        msg += f"\n対応: {self.spec.remediation}"
        super().__init__(msg)

    @property
    def exit_code(self) -> int:
        return self.spec.exit_code


def dependency_error(package: str, detail: str = "") -> KbError:
    return KbError("KB014", f"Missing dependency: {package}. {detail}".strip())
