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
  --help              Show this help text

Environment:
  DEER_FLOW_BUNDLE_ROOT, DEER_FLOW_VERSION, DEER_FLOW_NO_LOAD
EOF
}

die() {
    printf 'error: %s\n' "$1" >&2
    exit 1
}

log() {
    printf '%s\n' "$1"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_BUNDLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUNDLE_ROOT="${DEER_FLOW_BUNDLE_ROOT:-$DEFAULT_BUNDLE_ROOT}"
VERSION="${DEER_FLOW_VERSION:-}"
NO_LOAD="${DEER_FLOW_NO_LOAD:-0}"
COMMAND="up"

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
        find_bundle_file "deer-flow-images-$VERSION.tar" "deer-flow-images-$VERSION.tar"
    )" || die "could not find deer-flow-images-$VERSION.tar"
    SOURCE_TAR="$(
        find_bundle_file "deer-flow-source-$VERSION.tar.gz" "deer-flow-source-$VERSION.tar.gz"
    )" || die "could not find deer-flow-source-$VERSION.tar.gz"
else
    IMAGES_TAR="$(find_bundle_file 'deer-flow-images-*.tar' '')" || die "could not find a unique deer-flow-images-*.tar"
    SOURCE_TAR="$(find_bundle_file 'deer-flow-source-*.tar.gz' '')" || die "could not find a unique deer-flow-source-*.tar.gz"
    VERSION="$(basename "$IMAGES_TAR" | sed -E 's/^deer-flow-images-(.*)\.tar$/\1/')"
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
    rm -rf "$SOURCE_DIR"
    mkdir -p "$SOURCE_DIR"
    tar -xzf "$SOURCE_TAR" -C "$SOURCE_DIR"
}

seed_file() {
    local target="$1"
    local source="$2"
    if [ ! -f "$target" ]; then
        [ -f "$source" ] || die "missing seed source: $source"
        cp "$source" "$target"
    fi
}

seed_config() {
    local target="$RUNTIME_DIR/config.yaml"
    local source="$SOURCE_DIR/config.example.yaml"
    if [ -f "$target" ]; then
        return 0
    fi
    [ -f "$source" ] || die "missing seed source: $source"
    awk '
        /^[[:space:]]*models:[[:space:]]*$/ { print "models: []"; next }
        { print }
    ' "$source" > "$target"
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

    secret="$(generate_secret)"
    printf '%s\n' "$secret" > "$secret_file"
    chmod 600 "$secret_file"
    printf '%s\n' "$secret"
}

validate_runtime() {
    require_file "$RUNTIME_DIR/config.yaml"
    require_file "$RUNTIME_DIR/.env"
    require_file "$RUNTIME_DIR/frontend.env"
    require_file "$RUNTIME_DIR/extensions_config.json"
    require_file "$ENV_FILE"

    awk -v path="$RUNTIME_DIR/config.yaml" '
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
    ' "$RUNTIME_DIR/config.yaml"
}

append_env_if_missing() {
    local key="$1"
    local value="$2"

    if grep -q "^${key}=" "$ENV_FILE"; then
        return 0
    fi

    log "appending missing $key to $ENV_FILE"
    if [ -s "$ENV_FILE" ] && [ -n "$(tail -c 1 "$ENV_FILE")" ]; then
        printf '\n' >> "$ENV_FILE"
    fi
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
}

seed_runtime() {
    mkdir -p "$RUNTIME_DIR/data"

    seed_config
    seed_file "$RUNTIME_DIR/.env" "$SOURCE_DIR/.env.example"
    seed_file "$RUNTIME_DIR/frontend.env" "$SOURCE_DIR/frontend/.env.example"
    if [ ! -f "$RUNTIME_DIR/extensions_config.json" ]; then
        if [ -f "$SOURCE_DIR/extensions_config.example.json" ]; then
            cp "$SOURCE_DIR/extensions_config.example.json" "$RUNTIME_DIR/extensions_config.json"
        else
            printf '{"mcpServers":{},"skills":{}}\n' > "$RUNTIME_DIR/extensions_config.json"
        fi
    fi

    BETTER_AUTH_SECRET_VALUE="$(load_or_create_secret_file "$RUNTIME_DIR/data/.better-auth-secret")"
    DEER_FLOW_INTERNAL_AUTH_TOKEN_VALUE="$(load_or_create_secret_file "$RUNTIME_DIR/data/.internal-auth-token")"

    if [ ! -f "$ENV_FILE" ]; then
        cat > "$ENV_FILE" <<EOF
PORT=2026
DEER_FLOW_REPO_ROOT=$SOURCE_DIR
DEER_FLOW_HOME=$RUNTIME_DIR/data
DEER_FLOW_CONFIG_PATH=$RUNTIME_DIR/config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=$RUNTIME_DIR/extensions_config.json
DEER_FLOW_ENV_FILE=$RUNTIME_DIR/.env
DEER_FLOW_FRONTEND_ENV_FILE=$RUNTIME_DIR/frontend.env
DEER_FLOW_DOCKER_SOCKET=/var/run/docker.sock
BETTER_AUTH_SECRET=$BETTER_AUTH_SECRET_VALUE
DEER_FLOW_INTERNAL_AUTH_TOKEN=$DEER_FLOW_INTERNAL_AUTH_TOKEN_VALUE
DEER_FLOW_GATEWAY_IMAGE=deer-flow-gateway:$VERSION
DEER_FLOW_FRONTEND_IMAGE=deer-flow-frontend:$VERSION
NGINX_IMAGE=nginx:alpine
EOF
    fi

    append_env_if_missing "BETTER_AUTH_SECRET" "$BETTER_AUTH_SECRET_VALUE"
    append_env_if_missing "DEER_FLOW_INTERNAL_AUTH_TOKEN" "$DEER_FLOW_INTERNAL_AUTH_TOKEN_VALUE"
}

load_images() {
    if [ "$NO_LOAD" -eq 1 ]; then
        log "skipping docker load"
        return 0
    fi

    log "loading docker images..."
    docker load -i "$IMAGES_TAR"
}

compose_cmd() {
    docker compose -p deer-flow -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

wait_for_http() {
    local url="$1"
    local label="$2"
    local attempt
    if ! command -v curl >/dev/null 2>&1; then
        log "curl not found; skipping $label health check"
        return 0
    fi

    for attempt in $(seq 1 30); do
        if curl -fsS "$url" >/dev/null 2>&1; then
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

prepare_bundle() {
    extract_source
    seed_runtime
    validate_runtime
}

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
        prepare_bundle
        load_images
        log "starting services..."
        compose_cmd up -d --remove-orphans
        verify_services
        ;;
    restart)
        prepare_bundle
        load_images
        log "restarting services..."
        compose_cmd up -d --remove-orphans --force-recreate
        verify_services
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
