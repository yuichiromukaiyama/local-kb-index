#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

kb_require_macos
kb_require_command
kb_silent_env

root_arg="${1:-.}"
root="$(kb_abs_root "$root_arg")"
db="$(kb_db_path "$root")"

exec kb status --root "$root" --db "$db" --format json
