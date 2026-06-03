#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

START_TARGET=${START_TARGET:-start}
CONFIG_FILE=${CONFIG_FILE:-"$REPO_ROOT/config.yaml"}
REQUIRED_ENV_VARS=${REQUIRED_ENV_VARS:-DEEPSEEK_API_KEY}

usage() {
    cat <<'EOF'
Usage: sh scripts/start-local.sh [--print-command]

Starts the local iDeer stack from the repository root.

Environment variables:
  CONFIG_FILE         Path to the active config.yaml (default: ./config.yaml)
  START_TARGET        Make target to run (default: start)
  REQUIRED_ENV_VARS   Comma-separated env vars required before startup
                      (default: DEEPSEEK_API_KEY)
EOF
}

die() {
    printf 'error: %s\n' "$1" >&2
    exit 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

require_identifier() {
    case "$1" in
        "" | *[!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_]* | [!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_]*)
            die "invalid environment variable name: $1"
            ;;
    esac
}

require_make_target() {
    case "$1" in
        "" | *[!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.:-]*)
            die "invalid make target: $1"
            ;;
    esac
}

require_env_vars() {
    old_ifs=$IFS
    IFS=,
    for name in $REQUIRED_ENV_VARS; do
        case $name in
            "" ) continue ;;
        esac
        require_identifier "$name"
        eval "value=\${$name-}"
        [ -n "$value" ] || die "missing required environment variable: $name"
    done
    IFS=$old_ifs
}

print_only=0
case "${1:-}" in
    --print-command)
        print_only=1
        shift
        ;;
    -h|--help)
        usage
        exit 0
        ;;
esac

[ $# -eq 0 ] || die "unexpected argument: $1"

require_cmd make
require_cmd python3
require_cmd node
require_cmd pnpm
require_cmd uv
require_make_target "$START_TARGET"
require_env_vars
[ -f "$CONFIG_FILE" ] || die "missing config file: $CONFIG_FILE"

if [ "$print_only" -eq 1 ]; then
    printf 'cd %s && make %s\n' "$REPO_ROOT" "$START_TARGET"
    exit 0
fi

printf 'Starting iDeer from %s\n' "$REPO_ROOT"
printf 'Using config: %s\n' "$CONFIG_FILE"
cd "$REPO_ROOT"
exec make "$START_TARGET"
