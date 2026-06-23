from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .config import load_config, write_default_config, write_default_ignore
from .doctor import doctor
from .errors import KbError
from .evaluate import run_eval
from .indexer import index_full, prune, rebuild, sync
from .search import query, results_to_json
from .server import run_server
from .status import status
from .watch import watch


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args)
    except KbError as exc:
        if getattr(args, "format", "text") == "json":
            print(json.dumps({"ok": False, "error": {"code": exc.code, "message": str(exc), "remediation": exc.spec.remediation}}, ensure_ascii=False))
        else:
            _print_error(str(exc))
        return exc.exit_code
    except KeyboardInterrupt:
        _print_error("interrupted")
        return 130
    except Exception as exc:
        if getattr(args, "format", "text") == "json":
            print(json.dumps({"ok": False, "error": {"code": "KB000", "message": str(exc)}}, ensure_ascii=False))
        else:
            _print_error(f"KB000: unexpected error\n{exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kb", description="Local KB index/search CLI")
    p.add_argument("--version", action="store_true", help="Print version and exit")
    sub = p.add_subparsers(dest="command")

    def common(sp):
        sp.add_argument("--root", default=".", help="Workspace root. Relative paths are resolved from current directory.")
        sp.add_argument("--db", default=None, help="Index DB directory. Default: <root>/.kb_index")
        sp.add_argument("--config", default=None, help="Config file. Default: <root>/.kb/config.yml")
        sp.add_argument("--format", choices=["text", "json"], default="text")

    sp = sub.add_parser("init", help="Create .kb/config.yml and .kbignore")
    common(sp)
    sp.add_argument("--overwrite", action="store_true")

    sp = sub.add_parser("index", help="Build or refresh the full index")
    common(sp)
    sp.add_argument("--force", action="store_true", help="Drop and recreate the index")

    sp = sub.add_parser("sync", help="Incrementally update changed/new/deleted files")
    common(sp)

    sp = sub.add_parser("watch", help="Watch files and run sync in batches")
    common(sp)
    sp.add_argument("--once", action="store_true", help="Exit after the first sync")

    sp = sub.add_parser("query", help="Search the local index")
    common(sp)
    sp.add_argument("text", help="Search query")
    sp.add_argument("--mode", choices=["vector"], default="vector", help="Search mode. Only vector search is supported.")
    sp.add_argument("-n", "--limit", type=int, default=None)
    sp.add_argument("--copilot", action="store_true", help="Return compact JSON optimized for VS Code/Copilot tool output")
    sp.add_argument("--max-snippet-chars", type=int, default=None, help="Maximum snippet characters per result. Useful with --copilot.")
    sp.add_argument("--content", choices=["snippet", "none"], default="snippet", help="Result content detail. Use 'none' to return only path/range/score metadata.")

    sp = sub.add_parser("status", help="Show index status and stale-file counts")
    common(sp)
    sp.add_argument("--no-scan", action="store_true", help="Do not scan the workspace for stale files")

    sp = sub.add_parser("doctor", help="Diagnose dependencies, schema, DB, model, and VS Code integration")
    common(sp)
    sp.add_argument("--offline-check", action="store_true")

    sp = sub.add_parser("prune", help="Remove deleted files and stale chunks from the index")
    common(sp)

    sp = sub.add_parser("rebuild", help="Force rebuild the whole index")
    common(sp)
    sp.add_argument("--force", action="store_true")

    sp = sub.add_parser("config", help="Show resolved config")
    common(sp)
    sp.add_argument("--show", action="store_true")

    sp = sub.add_parser("eval", help="Run retrieval evaluation from .kb/eval.yml")
    common(sp)
    sp.add_argument("--file", default=".kb/eval.yml")
    sp.add_argument("-k", type=int, default=None)

    sp = sub.add_parser("serve", help="Run local HTTP query service")
    common(sp)
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8765)

    return p


def dispatch(args: argparse.Namespace) -> int:
    if args.version:
        print(__version__)
        return 0
    if not args.command:
        build_parser().print_help()
        return 2
    if args.command == "init":
        root = Path(args.root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        cfg_path = write_default_config(root, overwrite=args.overwrite)
        ign_path = write_default_ignore(root, overwrite=args.overwrite)
        return _emit({"ok": True, "config": str(cfg_path), "ignore": str(ign_path)}, args.format)
    cfg = load_config(args.root, getattr(args, "db", None), getattr(args, "config", None))
    if args.command == "index":
        return _emit(index_full(cfg, force=args.force), args.format)
    if args.command == "sync":
        return _emit(sync(cfg), args.format)
    if args.command == "watch":
        def show(result):
            if args.format == "json":
                print(json.dumps(_to_jsonable(result), ensure_ascii=False))
            else:
                print(f"synced: indexed_files={result.indexed_files} changed={result.changed_files} deleted={result.deleted_files} chunks={result.chunks}")
        watch(cfg, once=args.once, on_sync=show)
        return 0
    if args.command == "query":
        res = query(cfg, args.text, mode=args.mode, limit=args.limit, format_for_copilot=args.copilot)
        if args.format == "json" or args.copilot:
            max_snippet_chars = args.max_snippet_chars
            if args.copilot and max_snippet_chars is None:
                max_snippet_chars = 600
            payload = results_to_json(
                args.text,
                res,
                compact=args.copilot,
                content=args.content,
                max_snippet_chars=max_snippet_chars,
            )
            print(json.dumps(payload, ensure_ascii=False, separators=(",", ":") if args.copilot else None, indent=None if args.copilot else 2))
        else:
            _print_results(res)
        return 0
    if args.command == "status":
        st = status(cfg, scan=not args.no_scan)
        return _emit(st, args.format, exit_code=2 if st.stale else 0)
    if args.command == "doctor":
        d = doctor(cfg, offline_check=args.offline_check)
        return _emit(d, args.format, exit_code=0 if d.ok else 1)
    if args.command == "prune":
        return _emit(prune(cfg), args.format)
    if args.command == "rebuild":
        return _emit(rebuild(cfg, force=args.force), args.format)
    if args.command == "config":
        return _emit(cfg, args.format)
    if args.command == "eval":
        eval_path = Path(args.file)
        if not eval_path.is_absolute():
            eval_path = cfg.root / eval_path
        return _emit(run_eval(cfg, eval_path, k=args.k), args.format)
    if args.command == "serve":
        run_server(str(cfg.root), str(cfg.db), args.host, args.port)
        return 0
    return 2


def _emit(obj: Any, fmt: str, exit_code: int = 0) -> int:
    if fmt == "json":
        print(json.dumps(_to_jsonable(obj), ensure_ascii=False, indent=2))
    else:
        _print_text(obj)
    return exit_code


def _to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    return obj


def _print_text(obj: Any) -> None:
    data = _to_jsonable(obj)
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list):
                print(f"{k}:")
                for item in v:
                    print(f"  - {item}")
            elif isinstance(v, dict):
                print(f"{k}:")
                print(json.dumps(v, ensure_ascii=False, indent=2))
            else:
                print(f"{k}: {v}")
    else:
        print(data)


def _print_results(results) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        table = Table(show_lines=True)
        table.add_column("rank", justify="right")
        table.add_column("score", justify="right")
        table.add_column("file")
        table.add_column("range")
        table.add_column("symbol")
        table.add_column("snippet")
        for r in results:
            table.add_row(str(r.rank), f"{r.score:.3f}", r.path, f"{r.start_line}-{r.end_line}", r.symbol_name or r.heading_path or "", r.snippet)
        Console().print(table)
    except Exception:
        for r in results:
            print(f"[{r.rank}] {r.path}:{r.start_line}-{r.end_line} score={r.score:.3f}")
            if r.symbol_name or r.heading_path:
                print(f"    {r.symbol_name or r.heading_path}")
            print(r.snippet)
            print("---")


def _print_error(msg: str) -> None:
    print(msg, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
