#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

kb_require_macos
kb_require_command
kb_silent_env

root_arg="${1:-.}"
force="${2:-}"
root="$(kb_abs_root "$root_arg")"
db="$(kb_db_path "$root")"

if [ "$force" = "--force" ]; then
  exec kb rebuild --root "$root" --db "$db" --force --format json
fi

exec kb rebuild --root "$root" --db "$db" --format json
