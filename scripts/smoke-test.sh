#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
kb init --root "$ROOT"
kb doctor --root "$ROOT" || true
kb status --root "$ROOT" || true
