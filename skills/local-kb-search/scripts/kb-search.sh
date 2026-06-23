#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

QUERY="${1:-}"
ROOT_INPUT="${2:-.}"
N="${3:-5}"
SNIPPET="${4:-600}"
CONTENT="${5:-snippet}"
PATH_FILTER="${6:-}"
INCLUDE_CSV="${7:-}"
EXCLUDE_CSV="${8:-}"

if [[ -z "$QUERY" ]]; then
  kb_die "usage: kb-search.sh <query> [root] [n] [snippet_chars] [snippet|none] [path] [include_csv] [exclude_csv]"
fi

case "$CONTENT" in
  snippet|none) ;;
  *) kb_die "content must be 'snippet' or 'none': $CONTENT" ;;
esac

kb_require_command
kb_configure_quiet_ml_env

ROOT="$(kb_resolve_root "$ROOT_INPUT")"
DB="$(kb_default_db "$ROOT")"

kb_build_filter_args "$PATH_FILTER" "$INCLUDE_CSV" "$EXCLUDE_CSV"

exec kb query "$QUERY" \
  --root "$ROOT" \
  --db "$DB" \
  --mode vector \
  --copilot \
  --content "$CONTENT" \
  --max-snippet-chars "$SNIPPET" \
  -n "$N" \
  "${KB_FILTER_ARGS[@]}"
