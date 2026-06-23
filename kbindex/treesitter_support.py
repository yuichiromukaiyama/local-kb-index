from __future__ import annotations

from typing import Any

from .chunkers import ChunkResult, Symbol, _line_range, _split_large

LANG_MAP = {
    "typescript": "typescript",
    "typescriptreact": "tsx",
    "javascript": "javascript",
    "javascriptreact": "javascript",
    "python": "python",
}

SYMBOL_NODE_TYPES = {
    "function_declaration": "function",
    "function_definition": "function",
    "class_declaration": "class",
    "class_definition": "class",
    "method_definition": "method",
    "interface_declaration": "interface",
    "type_alias_declaration": "type",
    "lexical_declaration": "variable",
}


def try_tree_sitter_chunk(src: Any, config: Any, lang: str) -> ChunkResult | None:
    if not getattr(config.chunking, "use_tree_sitter", True):
        return None
    parser_lang = LANG_MAP.get(lang)
    if not parser_lang:
        return None
    try:
        from tree_sitter_languages import get_parser  # type: ignore
        parser = get_parser(parser_lang)
    except Exception:
        return None
    try:
        tree = parser.parse(src.text.encode("utf-8"))
        root = tree.root_node
        lines = src.text.splitlines()
        symbols: list[Symbol] = []
        chunks = []
        nodes = []
        _collect_symbol_nodes(root, nodes)
        # Use top-level and large declarations only, avoiding nested explosion.
        nodes = [n for n in nodes if n.start_point[0] != n.end_point[0]]
        nodes.sort(key=lambda n: (n.start_point[0], n.end_point[0]))
        filtered = []
        for n in nodes:
            if any(_contains(parent, n) for parent in filtered):
                continue
            filtered.append(n)
        if not filtered:
            return None
        for node in filtered:
            start = node.start_point[0] + 1
            end = node.end_point[0] + 1
            kind = SYMBOL_NODE_TYPES.get(node.type, node.type)
            name = _node_name(src.text.encode("utf-8"), node) or f"<{kind}>"
            symbols.append(Symbol(src.rel_path, name, kind, start, end))
            content = _line_range(lines, start, end)
            chunks.extend(_split_large(src, lang, start, content, config, symbol_name=name, symbol_kind=kind))
        return ChunkResult(chunks=chunks, symbols=symbols)
    except Exception:
        return None


def _collect_symbol_nodes(node: Any, out: list[Any]) -> None:
    if node.type in SYMBOL_NODE_TYPES:
        out.append(node)
    for child in node.children:
        _collect_symbol_nodes(child, out)


def _contains(parent: Any, child: Any) -> bool:
    return parent.start_byte <= child.start_byte and parent.end_byte >= child.end_byte and parent is not child


def _node_name(source: bytes, node: Any) -> str | None:
    for child in node.children:
        if child.type in {"identifier", "type_identifier", "property_identifier"}:
            return source[child.start_byte:child.end_byte].decode("utf-8", errors="ignore")
    # Some declarations have nested declarator/name nodes.
    stack = list(node.children)
    while stack:
        c = stack.pop(0)
        if c.type in {"identifier", "type_identifier", "property_identifier"}:
            return source[c.start_byte:c.end_byte].decode("utf-8", errors="ignore")
        stack.extend(c.children)
    return None
