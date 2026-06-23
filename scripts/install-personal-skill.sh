#!/usr/bin/env bash
set -Eeuo pipefail
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SKILL_SRC="$SRC_DIR/skills/local-kb-search"
DEST_DIR="$HOME/.copilot/skills/local-kb-search"
mkdir -p "$(dirname "$DEST_DIR")"
rm -rf "$DEST_DIR"
cp -R "$SKILL_SRC" "$DEST_DIR"
find "$DEST_DIR/scripts" -type f -name '*.sh' -exec chmod +x {} \;
printf 'Installed personal skill: %s\n' "$DEST_DIR"
