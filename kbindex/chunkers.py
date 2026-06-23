from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import AppConfig
from .scan import SourceFile


@dataclass
class Chunk:
    chunk_id: str
    file_path: str
    language: str
    symbol_name: str | None
    symbol_kind: str | None
    heading_path: str | None
    start_line: int
    end_line: int
    content: str
    parent_context: str | None = None
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    token_count: int = 0
    content_hash: str = ""


@dataclass
class Symbol:
    path: str
    name: str
    kind: str
    start_line: int
    end_line: int


@dataclass
class Edge:
    src_path: str
    dst: str
    edge_type: str
    evidence: str


@dataclass
class ChunkResult:
    chunks: list[Chunk]
    symbols: list[Symbol] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)


LANG_BY_SUFFIX = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".md": "markdown",
    ".mdx": "markdown",
    ".json": "json",
    ".jsonc": "jsonc",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".tf": "terraform",
    ".sql": "sql",
    ".toml": "toml",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
}


def detect_language(path: str) -> str:
    p = Path(path)
    if p.name.lower() == "dockerfile":
        return "dockerfile"
    return LANG_BY_SUFFIX.get(p.suffix.lower(), p.suffix.lower().lstrip(".") or "text")


def chunk_source(src: SourceFile, config: AppConfig) -> ChunkResult:
    lang = detect_language(src.rel_path)
    if lang == "markdown":
        return _chunk_markdown(src, config)
    if lang == "python":
        return _chunk_python(src, config)
    if lang in {"typescript", "typescriptreact", "javascript", "javascriptreact"}:
        try:
            from .treesitter_support import try_tree_sitter_chunk
            ts_result = try_tree_sitter_chunk(src, config, lang)
            if ts_result is not None and ts_result.chunks:
                return ts_result
        except Exception:
            pass
        return _chunk_js_ts(src, config, lang)
    if lang in {"json", "jsonc"}:
        return _chunk_json(src, config, lang)
    if lang == "yaml":
        return _chunk_yaml(src, config, lang)
    if lang == "terraform":
        return _chunk_terraform(src, config, lang)
    if lang == "sql":
        return _chunk_sql(src, config, lang)
    return _chunk_generic(src, config, lang)


def make_chunk_id(path: str, start: int, end: int, content_hash: str) -> str:
    raw = f"{path}:{start}:{end}:{content_hash}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def _mk(src: SourceFile, lang: str, start: int, end: int, content: str, *, symbol_name=None, symbol_kind=None, heading_path=None, parent_context=None, imports=None, exports=None) -> Chunk:
    content = content.strip("\n")
    chash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    return Chunk(
        chunk_id=make_chunk_id(src.rel_path, start, end, chash),
        file_path=src.rel_path,
        language=lang,
        symbol_name=symbol_name,
        symbol_kind=symbol_kind,
        heading_path=heading_path,
        start_line=start,
        end_line=end,
        content=content,
        parent_context=parent_context,
        imports=imports or [],
        exports=exports or [],
        token_count=max(1, len(content) // 4),
        content_hash=chash,
    )


def _line_range(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start - 1:end])


def _split_large(src: SourceFile, lang: str, start: int, text: str, config: AppConfig, **meta) -> list[Chunk]:
    max_chars = config.chunking.max_chars
    overlap = config.chunking.overlap_chars
    lines = text.splitlines()
    chunks: list[Chunk] = []
    if len(text) <= max_chars:
        end = start + len(lines) - 1 if lines else start
        chunks.append(_mk(src, lang, start, end, text, **meta))
        return chunks
    buf: list[str] = []
    buf_start = start
    char_count = 0
    for i, line in enumerate(lines, start=start):
        if char_count + len(line) + 1 > max_chars and buf:
            content = "\n".join(buf)
            chunks.append(_mk(src, lang, buf_start, i - 1, content, **meta))
            # overlap by approximate characters from the tail.
            tail = []
            n = 0
            for old in reversed(buf):
                tail.append(old)
                n += len(old) + 1
                if n >= overlap:
                    break
            tail = list(reversed(tail))
            buf_start = max(buf_start, i - len(tail))
            buf = tail[:]
            char_count = sum(len(x) + 1 for x in buf)
        buf.append(line)
        char_count += len(line) + 1
    if buf:
        chunks.append(_mk(src, lang, buf_start, start + len(lines) - 1, "\n".join(buf), **meta))
    return chunks


def _chunk_markdown(src: SourceFile, config: AppConfig) -> ChunkResult:
    lines = src.text.splitlines()
    chunks: list[Chunk] = []
    symbols: list[Symbol] = []
    headings: list[tuple[int, int, str]] = []
    in_code = False
    for i, line in enumerate(lines, start=1):
        if line.strip().startswith("```") or line.strip().startswith("~~~"):
            in_code = not in_code
        if not in_code:
            m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if m:
                headings.append((i, len(m.group(1)), m.group(2).strip()))
    if not headings:
        return _chunk_generic(src, config, "markdown")
    for idx, (line_no, level, title) in enumerate(headings):
        next_line = headings[idx + 1][0] - 1 if idx + 1 < len(headings) else len(lines)
        stack = [h[2] for h in headings[: idx + 1] if h[1] <= level]
        heading_path = " > ".join(stack)
        content = _line_range(lines, line_no, next_line)
        symbols.append(Symbol(src.rel_path, title, "heading", line_no, line_no))
        chunks.extend(_split_large(src, "markdown", line_no, content, config, heading_path=heading_path, symbol_name=title, symbol_kind="heading", parent_context=heading_path))
    return ChunkResult(chunks=chunks, symbols=symbols)


def _chunk_python(src: SourceFile, config: AppConfig) -> ChunkResult:
    lines = src.text.splitlines()
    chunks: list[Chunk] = []
    symbols: list[Symbol] = []
    edges: list[Edge] = []
    imports: list[str] = []
    try:
        tree = ast.parse(src.text)
    except SyntaxError:
        return _chunk_generic(src, config, "python")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
                edges.append(Edge(src.rel_path, alias.name, "IMPORTS", f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imports.append(mod)
            edges.append(Edge(src.rel_path, mod, "IMPORTS", f"from {mod} import ..."))
    top_nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    if not top_nodes:
        module_text = src.text
        chunks.extend(_split_large(src, "python", 1, module_text, config, imports=imports))
        return ChunkResult(chunks=chunks, symbols=symbols, edges=edges)
    # Add import/header chunk when useful.
    first_start = min(getattr(n, "lineno", 1) for n in top_nodes)
    if first_start > 1:
        header = _line_range(lines, 1, first_start - 1)
        if header.strip():
            chunks.extend(_split_large(src, "python", 1, header, config, symbol_name="<module-header>", symbol_kind="module", imports=imports))
    for node in top_nodes:
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start)
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        name = getattr(node, "name", "<anonymous>")
        symbols.append(Symbol(src.rel_path, name, kind, start, end))
        content = _line_range(lines, start, end)
        parent_context = _line_range(lines, max(1, start - 15), min(len(lines), end + 15))
        chunks.extend(_split_large(src, "python", start, content, config, symbol_name=name, symbol_kind=kind, parent_context=parent_context, imports=imports, exports=[name]))
    return ChunkResult(chunks=chunks, symbols=symbols, edges=edges)


def _chunk_js_ts(src: SourceFile, config: AppConfig, lang: str) -> ChunkResult:
    lines = src.text.splitlines()
    imports: list[str] = []
    exports: list[str] = []
    symbols: list[Symbol] = []
    edges: list[Edge] = []
    for line in lines:
        m = re.match(r"\s*import\s+.*?from\s+['\"](.+?)['\"]", line)
        if not m:
            m = re.match(r"\s*import\s+['\"](.+?)['\"]", line)
        if m:
            imports.append(m.group(1))
            edges.append(Edge(src.rel_path, m.group(1), "IMPORTS", line.strip()))
    pattern = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|const|let|var)\s+([A-Za-z0-9_$]+)")
    starts: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines, start=1):
        m = pattern.match(line)
        if m:
            name = m.group(1)
            kind = _js_kind(line)
            starts.append((i, name, kind))
            if "export" in line:
                exports.append(name)
    if not starts:
        chunks = _split_large(src, lang, 1, src.text, config, imports=imports, exports=exports)
        return ChunkResult(chunks=chunks, symbols=symbols, edges=edges)
    chunks: list[Chunk] = []
    if starts[0][0] > 1:
        header = _line_range(lines, 1, starts[0][0] - 1)
        if header.strip():
            chunks.extend(_split_large(src, lang, 1, header, config, symbol_name="<module-header>", symbol_kind="module", imports=imports, exports=exports))
    for idx, (start, name, kind) in enumerate(starts):
        end = starts[idx + 1][0] - 1 if idx + 1 < len(starts) else len(lines)
        symbols.append(Symbol(src.rel_path, name, kind, start, end))
        content = _line_range(lines, start, end)
        chunks.extend(_split_large(src, lang, start, content, config, symbol_name=name, symbol_kind=kind, imports=imports, exports=exports, parent_context=_line_range(lines, max(1, start - 10), min(len(lines), end + 10))))
    return ChunkResult(chunks=chunks, symbols=symbols, edges=edges)


def _js_kind(line: str) -> str:
    if "class " in line:
        return "class"
    if "interface " in line:
        return "interface"
    if "type " in line:
        return "type"
    if "function " in line:
        return "function"
    return "variable"


def _chunk_json(src: SourceFile, config: AppConfig, lang: str) -> ChunkResult:
    text = src.text
    if lang == "jsonc":
        text = re.sub(r"//.*?$|/\*.*?\*/", "", text, flags=re.S | re.M)
    try:
        obj = json.loads(text)
    except Exception:
        return _chunk_generic(src, config, lang)
    chunks: list[Chunk] = []
    symbols: list[Symbol] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            content = json.dumps({key: value}, ensure_ascii=False, indent=2)
            line = _find_line(src.text, f'"{key}"')
            symbols.append(Symbol(src.rel_path, str(key), "json-key", line, line))
            chunks.extend(_split_large(src, lang, line, content, config, symbol_name=str(key), symbol_kind="json-key"))
    else:
        chunks.extend(_split_large(src, lang, 1, src.text, config))
    return ChunkResult(chunks=chunks, symbols=symbols)


def _chunk_yaml(src: SourceFile, config: AppConfig, lang: str) -> ChunkResult:
    lines = src.text.splitlines()
    starts = []
    for i, line in enumerate(lines, start=1):
        if re.match(r"^[A-Za-z0-9_.-]+:\s*", line):
            starts.append((i, line.split(":", 1)[0].strip()))
    if not starts:
        return _chunk_generic(src, config, lang)
    chunks: list[Chunk] = []
    symbols: list[Symbol] = []
    for idx, (start, key) in enumerate(starts):
        end = starts[idx + 1][0] - 1 if idx + 1 < len(starts) else len(lines)
        symbols.append(Symbol(src.rel_path, key, "yaml-key", start, start))
        chunks.extend(_split_large(src, lang, start, _line_range(lines, start, end), config, symbol_name=key, symbol_kind="yaml-key"))
    return ChunkResult(chunks=chunks, symbols=symbols)


def _chunk_terraform(src: SourceFile, config: AppConfig, lang: str) -> ChunkResult:
    lines = src.text.splitlines()
    starts: list[tuple[int, str, str]] = []
    block_pat = re.compile(r'^\s*(resource|module|variable|output|data|locals|provider)\s+"?([^"\s{]+)?"?\s*"?([^"\s{]+)?"?')
    for i, line in enumerate(lines, start=1):
        m = block_pat.match(line)
        if m:
            kind = m.group(1)
            name = ".".join([x for x in [m.group(2), m.group(3)] if x]) or kind
            starts.append((i, name, kind))
    if not starts:
        return _chunk_generic(src, config, lang)
    chunks: list[Chunk] = []
    symbols: list[Symbol] = []
    for idx, (start, name, kind) in enumerate(starts):
        end = starts[idx + 1][0] - 1 if idx + 1 < len(starts) else len(lines)
        symbols.append(Symbol(src.rel_path, name, kind, start, end))
        chunks.extend(_split_large(src, lang, start, _line_range(lines, start, end), config, symbol_name=name, symbol_kind=kind))
    return ChunkResult(chunks=chunks, symbols=symbols)


def _chunk_sql(src: SourceFile, config: AppConfig, lang: str) -> ChunkResult:
    parts = re.split(r";\s*(?:\n|$)", src.text)
    chunks: list[Chunk] = []
    line = 1
    for part in parts:
        part = part.strip()
        if not part:
            continue
        nlines = part.count("\n") + 1
        name = _sql_name(part)
        chunks.extend(_split_large(src, lang, line, part, config, symbol_name=name, symbol_kind="sql-statement" if name else None))
        line += nlines
    return ChunkResult(chunks=chunks)


def _sql_name(text: str) -> str | None:
    m = re.search(r"(?i)\b(create|alter|drop)\s+(table|view|index|function|trigger)\s+([A-Za-z0-9_.\"]+)", text)
    if m:
        return m.group(3).strip('"')
    return None


def _chunk_generic(src: SourceFile, config: AppConfig, lang: str) -> ChunkResult:
    chunks = _split_large(src, lang, 1, src.text, config)
    return ChunkResult(chunks=chunks)


def _find_line(text: str, needle: str) -> int:
    for i, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return i
    return 1
