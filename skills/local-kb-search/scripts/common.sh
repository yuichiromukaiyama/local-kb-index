#!/usr/bin/env bash
set -Eeuo pipefail

kb_silent_env() {
  export HF_HUB_VERBOSITY="${HF_HUB_VERBOSITY:-error}"
  export HF_HUB_DISABLE_PROGRESS_BARS="${HF_HUB_DISABLE_PROGRESS_BARS:-1}"
  export TRANSFORMERS_VERBOSITY="${TRANSFORMERS_VERBOSITY:-error}"
  export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
  export TQDM_DISABLE="${TQDM_DISABLE:-1}"
  export KB_VERBOSE_ML="${KB_VERBOSE_ML:-0}"
}

kb_require_command() {
  if ! command -v kb >/dev/null 2>&1; then
    printf '%s\n' '{"error":"kb command not found on PATH"}' >&2
    exit 127
  fi
}

kb_require_macos() {
  local os_name
  os_name="$(uname -s)"
  if [ "$os_name" != "Darwin" ]; then
    printf '%s\n' '{"error":"this local-kb skill is intended for macOS only"}' >&2
    exit 2
  fi
}

kb_abs_root() {
  local root="${1:-.}"
  if [ ! -d "$root" ]; then
    printf '{"error":"root directory not found","root":"%s"}\n' "$root" >&2
    exit 2
  fi
  (cd "$root" && pwd -P)
}

kb_db_path() {
  local root="$1"
  printf '%s/.kb_index\n' "$root"
}
