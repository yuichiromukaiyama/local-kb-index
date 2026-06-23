#!/usr/bin/env bash
set -Eeuo pipefail
DEST_DIR="$HOME/.copilot/skills/local-kb-search"
rm -rf "$DEST_DIR"
printf 'Removed personal skill: %s\n' "$DEST_DIR"
