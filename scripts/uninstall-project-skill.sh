#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${1:-.}"
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd -P)"
DEST_DIR="$PROJECT_ROOT/.github/skills/local-kb-search"
rm -rf "$DEST_DIR"
printf 'Removed project skill: %s\n' "$DEST_DIR"
