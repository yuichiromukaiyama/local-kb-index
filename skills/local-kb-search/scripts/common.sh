#!/usr/bin/env bash
set -euo pipefail

kb_die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

kb_require_command() {
  command -v kb >/dev/null 2>&1 || kb_die "kb command was not found in PATH"
}

kb_resolve_root() {
  local root="${1:-.}"
  if [[ ! -d "$root" ]]; then
    kb_die "root directory does not exist: $root"
  fi
  (cd "$root" && pwd -P)
}

kb_default_db() {
  local root="$1"
  printf '%s/.kb_index' "$root"
}

kb_configure_quiet_ml_env() {
  export HF_HUB_VERBOSITY="${HF_HUB_VERBOSITY:-error}"
  export HF_HUB_DISABLE_PROGRESS_BARS="${HF_HUB_DISABLE_PROGRESS_BARS:-1}"
  export TRANSFORMERS_VERBOSITY="${TRANSFORMERS_VERBOSITY:-error}"
  export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
  export TQDM_DISABLE="${TQDM_DISABLE:-1}"
}

# Builds global array KB_FILTER_ARGS from optional path/include/exclude inputs.
# Arguments:
#   1. path filter: single repo-relative directory, file, or glob
#   2. include CSV: comma-separated include globs
#   3. exclude CSV: comma-separated exclude globs
kb_build_filter_args() {
  local path_filter="${1:-}"
  local include_csv="${2:-}"
  local exclude_csv="${3:-}"
  local item

  KB_FILTER_ARGS=()

  if [[ -n "$path_filter" ]]; then
    KB_FILTER_ARGS+=(--path "$path_filter")
  fi

  if [[ -n "$include_csv" ]]; then
    local old_ifs="$IFS"
    IFS=','
    read -ra include_items <<< "$include_csv"
    IFS="$old_ifs"
    for item in "${include_items[@]}"; do
      item="${item#${item%%[![:space:]]*}}"
      item="${item%${item##*[![:space:]]}}"
      if [[ -n "$item" ]]; then
        KB_FILTER_ARGS+=(--include "$item")
      fi
    done
  fi

  if [[ -n "$exclude_csv" ]]; then
    local old_ifs="$IFS"
    IFS=','
    read -ra exclude_items <<< "$exclude_csv"
    IFS="$old_ifs"
    for item in "${exclude_items[@]}"; do
      item="${item#${item%%[![:space:]]*}}"
      item="${item%${item##*[![:space:]]}}"
      if [[ -n "$item" ]]; then
        KB_FILTER_ARGS+=(--exclude "$item")
      fi
    done
  fi
}
