#!/usr/bin/env bash
set -Eeuo pipefail
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SKILL_SRC="$SRC_DIR/skills/local-kb-search"
PROJECT_ROOT="${1:-.}"
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd -P)"
DEST_DIR="$PROJECT_ROOT/.github/skills/local-kb-search"
mkdir -p "$(dirname "$DEST_DIR")"
rm -rf "$DEST_DIR"
cp -R "$SKILL_SRC" "$DEST_DIR"
find "$DEST_DIR/scripts" -type f -name '*.sh' -exec chmod +x {} \;
printf 'Installed project skill: %s\n' "$DEST_DIR"
