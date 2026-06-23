#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

kb_require_macos
kb_require_command
kb_silent_env

query="${1:-}"
root_arg="${2:-.}"
top_k="${3:-5}"
max_snippet_chars="${4:-600}"
content="${5:-snippet}"

if [ -z "$query" ]; then
  printf '%s\n' '{"error":"query is required"}' >&2
  exit 2
fi

root="$(kb_abs_root "$root_arg")"
db="$(kb_db_path "$root")"

exec kb query "$query" \
  --root "$root" \
  --db "$db" \
  --mode vector \
  --copilot \
  --content "$content" \
  --max-snippet-chars "$max_snippet_chars" \
  -n "$top_k"
