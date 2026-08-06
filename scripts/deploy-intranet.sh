#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: deploy-intranet.sh [options] [command]

Commands:
  prepare   Extract source tar and seed runtime config files
  load      Load offline Docker images
  up        Prepare, load images, then start services (default)
  start     Alias of up
  restart   Prepare, load images, then restart services
  stop      Stop services
  down      Alias of stop
  status    Show docker compose status
  logs      Follow service logs

Options:
  --version <value>   Use a specific bundle version
  --bundle-root <dir> Use a specific bundle directory
  --no-load           Skip docker load when running up/start/restart
  --skip-check        Skip the pre-deployment environment check
  --dry-run           Show what would be done without executing
  --help              Show this help text

Environment:
  IDEER_BUNDLE_ROOT, IDEER_VERSION, IDEER_NO_LOAD
EOF
}

die() {
    printf 'error: %s\n' "$1" >&2
    exit 1
}

log() {
    printf '%s\n' "$1"
}

warn() {
    printf 'warning: %s\n' "$1" >&2
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$(basename "$SCRIPT_DIR")" = "scripts" ]; then
    DEFAULT_BUNDLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    DEFAULT_BUNDLE_ROOT="$SCRIPT_DIR"
fi
BUNDLE_ROOT="${IDEER_BUNDLE_ROOT:-$DEFAULT_BUNDLE_ROOT}"
VERSION="${IDEER_VERSION:-}"
NO_LOAD="${IDEER_NO_LOAD:-0}"
COMMAND="up"
SKIP_CHECK=0
DRY_RUN=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --version)
            [ "$#" -ge 2 ] || die "--version requires a value"
            VERSION="$2"
            shift 2
            ;;
        --bundle-root)
            [ "$#" -ge 2 ] || die "--bundle-root requires a value"
            BUNDLE_ROOT="$2"
            shift 2
            ;;
        --no-load)
            NO_LOAD=1
            shift
            ;;
        --skip-check)
            SKIP_CHECK=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        up|start|prepare|load|restart|stop|down|status|logs)
            COMMAND="$1"
            shift
            if [ "$COMMAND" = "logs" ] && [ "$#" -gt 0 ]; then
                LOG_SERVICE="$1"
                shift
            else
                LOG_SERVICE=""
            fi
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

BUNDLE_ROOT="$(cd "$BUNDLE_ROOT" && pwd)"

# ---------------------------------------------------------------------------
# Pre-deployment check
# ---------------------------------------------------------------------------
run_pre_check() {
    if [ "$SKIP_CHECK" -eq 1 ]; then
        log "skipping pre-deployment check (--skip-check)"
        return 0
    fi

    local check_script="$SCRIPT_DIR/check-intranet.sh"
    if [ ! -x "$check_script" ]; then
        warn "pre-check script not found or not executable: $check_script"
        warn "skipping pre-deployment check"
        return 0
    fi

    log "running pre-deployment check..."
    if ! "$check_script"; then
        die "pre-deployment check failed. Fix the issues above and retry, or use --skip-check to bypass."
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# Dry-run wrapper
# ---------------------------------------------------------------------------
run_cmd() {
    if [ "$DRY_RUN" -eq 1 ]; then
        log "[dry-run] $*"
        return 0
    fi
    "$@"
}

if ! command -v docker >/dev/null 2>&1; then
    die "docker is required"
fi

if ! docker compose version >/dev/null 2>&1; then
    die "docker compose v2 is required"
fi

require_file() {
    [ -f "$1" ] || die "missing file: $1"
}

generate_secret() {
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import secrets; print(secrets.token_hex(32))'
        return 0
    fi

    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 32
        return 0
    fi

    die "python3 or openssl is required to generate secrets"
}

find_bundle_file() {
    local pattern="$1"
    local exact="$2"
    local matches=()
    local dir
    for dir in "$BUNDLE_ROOT" "$BUNDLE_ROOT/.." "$BUNDLE_ROOT/../.."; do
        if [ -n "$exact" ] && [ -f "$dir/$exact" ]; then
            printf '%s\n' "$dir/$exact"
            return 0
        fi
        shopt -s nullglob
        matches=("$dir"/$pattern)
        shopt -u nullglob
        if [ "${#matches[@]}" -eq 1 ]; then
            printf '%s\n' "${matches[0]}"
            return 0
        fi
    done
    return 1
}

if [ -n "$VERSION" ]; then
    IMAGES_TAR="$(
        find_bundle_file "ideer-images-$VERSION.tar" "ideer-images-$VERSION.tar"
    )" || die "could not find ideer-images-$VERSION.tar"
    SOURCE_TAR="$(
        find_bundle_file "ideer-source-$VERSION.tar.gz" "ideer-source-$VERSION.tar.gz"
    )" || die "could not find ideer-source-$VERSION.tar.gz"
else
    IMAGES_TAR="$(find_bundle_file 'ideer-images-*.tar' '')" || die "could not find a unique ideer-images-*.tar"
    SOURCE_TAR="$(find_bundle_file 'ideer-source-*.tar.gz' '')" || die "could not find a unique ideer-source-*.tar.gz"
    VERSION="$(basename "$IMAGES_TAR" | sed -E 's/^ideer-images-(.*)\.tar$/\1/')"
fi

SOURCE_DIR="$BUNDLE_ROOT/source"
RUNTIME_DIR="$BUNDLE_ROOT/runtime"
ENV_FILE="$BUNDLE_ROOT/env.intranet"
COMPOSE_FILE="$SOURCE_DIR/docker/docker-compose.intranet.yaml"
IMAGES_BASENAME="$(basename "$IMAGES_TAR")"
SOURCE_BASENAME="$(basename "$SOURCE_TAR")"

extract_source() {
    if [ -d "$SOURCE_DIR/backend" ] && [ -d "$SOURCE_DIR/frontend" ] && [ -d "$SOURCE_DIR/docker" ]; then
        return 0
    fi

    log "extracting source tar..."
    run_cmd rm -rf "$SOURCE_DIR"
    run_cmd mkdir -p "$SOURCE_DIR"
    run_cmd tar -xzf "$SOURCE_TAR" -C "$SOURCE_DIR"
}

seed_file() {
    local target="$1"
    local source="$2"
    if [ ! -f "$target" ]; then
        [ -f "$source" ] || die "missing seed source: $source"
        run_cmd cp "$source" "$target"
    fi
}

seed_config() {
    local target="$RUNTIME_DIR/config.yaml"
    local source="$SOURCE_DIR/config.intranet.yaml"
    # Fall back to config.example.yaml if config.intranet.yaml is not in the bundle
    if [ ! -f "$source" ]; then
        source="$SOURCE_DIR/config.example.yaml"
    fi
    if [ -f "$target" ]; then
        return 0
    fi
    [ -f "$source" ] || die "missing seed source: $source"
    if [ "$DRY_RUN" -eq 1 ]; then
        log "[dry-run] generate $target from $source (with models: [])"
        return 0
    fi
    awk '
        /^[[:space:]]*models:[[:space:]]*$/ { print "models: []"; next }
        { print }
    ' "$source" > "$target"
}

# Ensure agents_api.enabled is true so the custom-agent management API
# (including the bundled fault-zeroing agent) is accessible after deploy.
# config.example.yaml ships with agents_api.enabled: false; this patches
# it to true.  Idempotent: no-ops if already true or if agents_api block
# is absent.
patch_agents_api_enabled() {
    local config="$RUNTIME_DIR/config.yaml"
    [ -f "$config" ] || return 0

    if grep -A1 '^agents_api:' "$config" | grep -q 'enabled: false'; then
        log "enabling agents_api in $config ..."
        run_cmd sed -i '/^agents_api:/{n;s/enabled: false/enabled: true/;}' "$config"
    fi
}

load_or_create_secret_file() {
    local secret_file="$1"
    local secret
    if [ -f "$secret_file" ]; then
        secret="$(tr -d '\r\n' < "$secret_file")"
        if [ -n "$secret" ]; then
            printf '%s\n' "$secret"
            return 0
        fi
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        printf '%s\n' "<dry-run-placeholder-secret>"
        return 0
    fi

    secret="$(generate_secret)"
    printf '%s\n' "$secret" > "$secret_file"
    chmod 600 "$secret_file"
    printf '%s\n' "$secret"
}

validate_runtime() {
    require_file "$ENV_FILE"

    # shellcheck disable=SC1090
    . "$ENV_FILE"

    local config_path="${IDEER_CONFIG_PATH:-$RUNTIME_DIR/config.yaml}"
    local backend_env_path="${IDEER_ENV_FILE:-$RUNTIME_DIR/.env}"
    local frontend_env_path="${IDEER_FRONTEND_ENV_FILE:-$RUNTIME_DIR/frontend.env}"
    local extensions_config_path="${IDEER_EXTENSIONS_CONFIG_PATH:-$RUNTIME_DIR/extensions_config.json}"

    require_file "$config_path"
    require_file "$backend_env_path"
    require_file "$frontend_env_path"
    require_file "$extensions_config_path"

    awk -v path="$config_path" '
        function fail() {
            print path ": models must be a list" > "/dev/stderr"
            exit 1
        }
        /^models:[[:space:]]*$/ {
            in_models = 1
            found = 1
            next
        }
        /^models:[[:space:]]*\[/ {
            found = 1
            in_models = 0
            next
        }
        /^models:[[:space:]]*null[[:space:]]*$/ {
            found = 1
            fail()
        }
        in_models {
            if ($0 ~ /^[[:space:]]*($|#)/) {
                next
            }
            if ($0 ~ /^[[:space:]]*-/) {
                in_models = 0
                next
            }
            fail()
        }
        END {
            if (in_models) {
                fail()
            }
        }
    ' "$config_path"
}

append_env_if_missing() {
    local key="$1"
    local value="$2"

    if grep -q "^${key}=" "$ENV_FILE"; then
        return 0
    fi

    log "appending missing $key to $ENV_FILE"
    if [ "$DRY_RUN" -eq 1 ]; then
        return 0
    fi
    if [ -s "$ENV_FILE" ] && [ -n "$(tail -c 1 "$ENV_FILE")" ]; then
        printf '\n' >> "$ENV_FILE"
    fi
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
}

seed_runtime() {
    run_cmd mkdir -p "$RUNTIME_DIR/data"

    seed_config
    patch_agents_api_enabled
    seed_file "$RUNTIME_DIR/.env" "$SOURCE_DIR/.env.example"
    seed_file "$RUNTIME_DIR/frontend.env" "$SOURCE_DIR/frontend/.env.example"
    if [ ! -f "$RUNTIME_DIR/extensions_config.json" ]; then
        if [ -f "$SOURCE_DIR/extensions_config.example.json" ]; then
            run_cmd cp "$SOURCE_DIR/extensions_config.example.json" "$RUNTIME_DIR/extensions_config.json"
        else
            if [ "$DRY_RUN" -eq 1 ]; then
                log "[dry-run] create $RUNTIME_DIR/extensions_config.json"
            else
                printf '{"mcpServers":{},"skills":{}}\n' > "$RUNTIME_DIR/extensions_config.json"
            fi
        fi
    fi

    BETTER_AUTH_SECRET_VALUE="$(load_or_create_secret_file "$RUNTIME_DIR/data/.better-auth-secret")"
    IDEER_INTERNAL_AUTH_TOKEN_VALUE="$(load_or_create_secret_file "$RUNTIME_DIR/data/.internal-auth-token")"

    if [ ! -f "$ENV_FILE" ]; then
        if [ "$DRY_RUN" -eq 1 ]; then
            log "[dry-run] create $ENV_FILE"
        else
            cat > "$ENV_FILE" <<EOF
PORT=2026
IDEER_REPO_ROOT=$SOURCE_DIR
IDEER_HOME=$RUNTIME_DIR/data
IDEER_CONFIG_PATH=$RUNTIME_DIR/config.yaml
IDEER_EXTENSIONS_CONFIG_PATH=$RUNTIME_DIR/extensions_config.json
IDEER_ENV_FILE=$RUNTIME_DIR/.env
IDEER_FRONTEND_ENV_FILE=$RUNTIME_DIR/frontend.env
IDEER_DOCKER_SOCKET=/var/run/docker.sock
BETTER_AUTH_SECRET=$BETTER_AUTH_SECRET_VALUE
IDEER_INTERNAL_AUTH_TOKEN=$IDEER_INTERNAL_AUTH_TOKEN_VALUE
IDEER_GATEWAY_IMAGE=ideer-gateway:$VERSION
IDEER_FRONTEND_IMAGE=ideer-frontend:$VERSION
NGINX_IMAGE=nginx:alpine
IDEER_NETWORK_MODE=offline
EOF
        fi
    fi

    append_env_if_missing "BETTER_AUTH_SECRET" "$BETTER_AUTH_SECRET_VALUE"
    append_env_if_missing "IDEER_INTERNAL_AUTH_TOKEN" "$IDEER_INTERNAL_AUTH_TOKEN_VALUE"
    append_env_if_missing "IDEER_NETWORK_MODE" "offline"
}

load_images() {
    if [ "$NO_LOAD" -eq 1 ]; then
        log "skipping docker load"
        return 0
    fi

    log "loading docker images..."
    run_cmd docker load -i "$IMAGES_TAR"
}

compose_cmd() {
    run_cmd docker compose -p ideer -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

http_ok() {
    local url="$1"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS "$url" >/dev/null 2>&1
        return $?
    fi

    if command -v wget >/dev/null 2>&1; then
        wget -q -O- "$url" >/dev/null 2>&1
        return $?
    fi

    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=5).read()' "$url" >/dev/null 2>&1
        return $?
    fi

    if command -v python >/dev/null 2>&1; then
        python -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=5).read()' "$url" >/dev/null 2>&1
        return $?
    fi

    die "curl, wget, python3, or python is required for HTTP health checks"
}

wait_for_http() {
    local url="$1"
    local label="$2"
    local attempt

    for attempt in $(seq 1 30); do
        if http_ok "$url"; then
            log "$label is healthy: $url"
            return 0
        fi
        sleep 2
    done

    die "$label health check failed: $url. Run './deploy-intranet.sh logs gateway' and './deploy-intranet.sh logs frontend' for details."
}

verify_services() {
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    wait_for_http "http://127.0.0.1:${PORT:-2026}/health" "gateway"
    wait_for_http "http://127.0.0.1:${PORT:-2026}/api/v1/auth/setup-status" "auth setup-status"
    wait_for_http "http://127.0.0.1:${PORT:-2026}/" "frontend"
}

print_rollback_instructions() {
    cat >&2 <<'EOF'

=== Rollback Instructions ===
If the deployment failed, you can recover using these steps:

1. Stop the services:
   ./deploy-intranet.sh stop

2. Check service logs for errors:
   ./deploy-intranet.sh logs gateway
   ./deploy-intranet.sh logs frontend
   ./deploy-intranet.sh logs nginx

3. If images are corrupted, re-load them:
   ./deploy-intranet.sh load

4. If config is corrupted, remove the runtime directory and re-prepare:
   rm -rf runtime/
   ./deploy-intranet.sh prepare

5. Full reset (stop, clean, re-deploy):
   ./deploy-intranet.sh stop
   rm -rf runtime/ source/ env.intranet
   ./deploy-intranet.sh up

6. If Docker containers are stuck:
   docker compose -p ideer down --remove-orphans
   docker system prune -f
EOF
}

prepare_bundle() {
    extract_source
    seed_runtime
    validate_runtime
}

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

# Run pre-check for commands that modify state
case "$COMMAND" in
    up|start|restart|prepare)
        run_pre_check
        ;;
esac

if [ "$DRY_RUN" -eq 1 ]; then
    log "=== DRY RUN MODE ==="
    log "No changes will be made. Commands that would run are shown below."
    echo ""
fi

case "$COMMAND" in
    prepare)
        prepare_bundle
        log "prepared source: $SOURCE_DIR"
        log "prepared runtime: $RUNTIME_DIR"
        log "env file: $ENV_FILE"
        ;;
    load)
        load_images
        ;;
    up|start)
        if ! prepare_bundle; then
            print_rollback_instructions
            die "prepare step failed"
        fi
        load_images
        log "starting services..."
        if ! compose_cmd up -d --remove-orphans; then
            print_rollback_instructions
            die "failed to start services"
        fi
        if [ "$DRY_RUN" -eq 0 ]; then
            verify_services
        fi
        log "deployment complete"
        ;;
    restart)
        if ! prepare_bundle; then
            print_rollback_instructions
            die "prepare step failed"
        fi
        load_images
        log "restarting services..."
        if ! compose_cmd up -d --remove-orphans --force-recreate; then
            print_rollback_instructions
            die "failed to restart services"
        fi
        if [ "$DRY_RUN" -eq 0 ]; then
            verify_services
        fi
        log "restart complete"
        ;;
    stop|down)
        prepare_bundle
        if [ -f "$COMPOSE_FILE" ]; then
            compose_cmd down
        else
            die "compose file not found: $COMPOSE_FILE"
        fi
        ;;
    status)
        prepare_bundle
        if [ -f "$COMPOSE_FILE" ]; then
            compose_cmd ps
        else
            die "compose file not found: $COMPOSE_FILE"
        fi
        ;;
    logs)
        prepare_bundle
        if [ -f "$COMPOSE_FILE" ]; then
            if [ -n "${LOG_SERVICE:-}" ]; then
                compose_cmd logs -f "$LOG_SERVICE"
            else
                compose_cmd logs -f
            fi
        else
            die "compose file not found: $COMPOSE_FILE"
        fi
        ;;
esac
