#!/usr/bin/env bash
set -Eeuo pipefail
if [ "$(uname -s)" != "Darwin" ]; then
  printf 'This helper is intended for macOS only.\n' >&2
  exit 2
fi
if ! command -v kb >/dev/null 2>&1; then
  printf 'kb command not found on PATH.\n' >&2
  exit 127
fi
printf 'macOS and kb command are available.\n'
kb --help >/dev/null || true
