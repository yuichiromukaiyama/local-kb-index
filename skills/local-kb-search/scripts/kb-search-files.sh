#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

QUERY="${1:-}"
ROOT_INPUT="${2:-.}"
N="${3:-8}"
PATH_FILTER="${4:-}"
INCLUDE_CSV="${5:-}"
EXCLUDE_CSV="${6:-}"

if [[ -z "$QUERY" ]]; then
  kb_die "usage: kb-search-files.sh <query> [root] [n] [path] [include_csv] [exclude_csv]"
fi

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
  --content none \
  -n "$N" \
  "${KB_FILTER_ARGS[@]}"
