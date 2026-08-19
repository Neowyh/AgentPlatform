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
  prune-old Remove old ideer-gateway:* / ideer-frontend:* image tags, keeping
            the current version plus --keep-versions recent versions

Options:
  --version <value>   Use a specific bundle version
  --bundle-root <dir> Use a specific bundle directory
  --bundled-conflict <keep|override>
                    How to handle bundled resources modified after install
                    on upgrade: keep (default) preserves user changes and
                    skips the bundled update, override publishes the bundled
                    content as a new version
  --keep-versions <n> Number of recent versions to keep when pruning old
                      images (default: 2, 0 = keep only the current version)
  --prune-old         After a successful up/restart, remove old
                      ideer-gateway:* / ideer-frontend:* image tags
  --no-load           Skip docker load when running up/start/restart
  --skip-check        Skip the pre-deployment environment check
  --dry-run           Show what would be done without executing
  --help              Show this help text

Environment:
  IDEER_BUNDLE_ROOT, IDEER_VERSION, IDEER_NO_LOAD
  IDEER_ADMIN_EMAIL, IDEER_ADMIN_PASSWORD override the auto-created super admin
    credentials (default: super_admin@test.com / super_admin@test.com)
  IDEER_INSTALL_FAULT_ZEROING=0 skips installing the bundled fault-zeroing agent
  IDEER_INSTALL_SRS_WRITING=0 skips installing the bundled srs-writing agent
  IDEER_BUNDLED_CONFLICT=keep|override same as --bundled-conflict
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
PRUNE_OLD=0
KEEP_VERSIONS=2
BUNDLED_CONFLICT="${IDEER_BUNDLED_CONFLICT:-keep}"

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
        --bundled-conflict)
            [ "$#" -ge 2 ] || die "--bundled-conflict requires a value"
            BUNDLED_CONFLICT="$2"
            shift 2
            ;;
        --no-load)
            NO_LOAD=1
            shift
            ;;
        --prune-old)
            PRUNE_OLD=1
            shift
            ;;
        --keep-versions)
            [ "$#" -ge 2 ] || die "--keep-versions requires a value"
            KEEP_VERSIONS="$2"
            shift 2
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
        up|start|prepare|load|restart|stop|down|status|logs|prune-old)
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

case "$BUNDLED_CONFLICT" in
    keep|override) ;;
    *) die "--bundled-conflict must be keep or override" ;;
esac

case "$KEEP_VERSIONS" in
    ''|*[!0-9]*) die "--keep-versions must be a non-negative integer (got '$KEEP_VERSIONS')" ;;
esac

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
    local marker="$SOURCE_DIR/.bundle-version"
    if [ -d "$SOURCE_DIR/backend" ] && [ -d "$SOURCE_DIR/frontend" ] && [ -d "$SOURCE_DIR/docker" ]; then
        if [ -f "$marker" ] && [ "$(cat "$marker")" = "$VERSION" ]; then
            return 0
        fi
        log "source tree is from bundle version $(cat "$marker" 2>/dev/null || echo unknown); extracting $VERSION"
    fi

    log "extracting source tar..."
    run_cmd rm -rf "$SOURCE_DIR"
    run_cmd mkdir -p "$SOURCE_DIR"
    run_cmd tar -xzf "$SOURCE_TAR" -C "$SOURCE_DIR"
    run_cmd printf '%s\n' "$VERSION" > "$marker"
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
    # Replace the whole models block (including trailing example entries and
    # their comments) with an empty list; otherwise the seeded config keeps
    # dangling "- name:" items that make the YAML invalid.
    awk '
        function blank_or_comment(l) {
            return l ~ /^[[:space:]]*$/ || l ~ /^[[:space:]]*#/
        }
        /^[[:space:]]*models:[[:space:]]*$/ {
            print "models: []"
            in_models = 1
            next
        }
        in_models {
            if (blank_or_comment($0) || $0 ~ /^[[:space:]]/ || $0 ~ /^[[:space:]]*-/) {
                next
            }
            in_models = 0
        }
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

# The config template ships an officecli sandbox mount whose host_path is a
# placeholder (e.g. /opt/deer-flow/vendor/officecli/officecli).  When the seeded
# runtime config points at a path that does not exist, rewrite it to the bundle's
# own vendor/officecli binary so the sandbox can inject it offline.  Idempotent:
# a user-customized host_path that actually exists is left untouched.
patch_officecli_mount() {
    local config="$RUNTIME_DIR/config.yaml"
    local bundled_bin="$SOURCE_DIR/vendor/officecli/officecli"
    [ -f "$config" ] || return 0
    [ -f "$bundled_bin" ] || return 0

    local current
    current="$(grep -B1 'container_path: /usr/local/bin/officecli' "$config" | grep 'host_path:' | sed -E "s/.*host_path:[[:space:]]*['\"]?([^[:space:]'\"]*).*/\1/" | head -1 || true)"
    [ -n "$current" ] || return 0
    [ -e "$current" ] && return 0

    log "patching officecli mount host_path: $current -> $bundled_bin"
    run_cmd sed -i "s|host_path: ${current}|host_path: ${bundled_bin}|" "$config"
}

# When the sandbox image is bundled with the bundle (ideer-sandbox:<version>)
# and the seeded runtime config still references a placeholder or default
# sandbox image (an external registry placeholder, the public default, or a
# version-less ideer-sandbox:latest template value) that is NOT present
# locally, rewrite sandbox.image to the bundled tag so the AIO sandbox can
# start offline. Idempotent: a user-customized image name that is already
# present locally is left untouched.
patch_sandbox_image() {
    local config="$RUNTIME_DIR/config.yaml"
    local image="ideer-sandbox:$VERSION"
    [ -f "$config" ] || return 0

    docker image inspect "$image" >/dev/null 2>&1 || return 0

    local provider current
    provider="$(awk '/^sandbox:/{f=1;next} f&&/^[^[:space:]]/{exit} f&&/^[[:space:]]*use:/{sub(/^[[:space:]]*use:[[:space:]]*/,"");print;exit}' "$config" 2>/dev/null || true)"
    [ "$provider" = "ideer.community.aio_sandbox:AioSandboxProvider" ] || return 0

    current="$(awk '/^sandbox:/{f=1;next} f&&/^[^[:space:]]/{exit} f&&/^[[:space:]]*image:/{sub(/^[[:space:]]*image:[[:space:]]*/,"");gsub(/"/,"");print;exit}' "$config" 2>/dev/null || true)"
    [ -n "$current" ] || return 0
    [ "$current" = "$image" ] && return 0

    if echo "$current" | grep -qE 'harbor\.internal\.com|cr\.volces\.com|^ideer-sandbox:'; then
        if docker image inspect "$current" >/dev/null 2>&1; then
            return 0
        fi
        log "patching sandbox image: $current -> $image"
        run_cmd sed -i "s|image: ${current}|image: ${image}|" "$config"
        append_env_if_missing "IDEER_SANDBOX_IMAGE" "$image"
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

    # Soft check: when the AIO sandbox provider is configured, warn if its
    # image is not present in the local Docker daemon (sandboxed tools will
    # fail at runtime). Not fatal: the operator may load the image later or
    # switch sandbox.use to a provider that needs no image.
    local sandbox_provider sandbox_image
    sandbox_provider="$(awk '/^sandbox:/{f=1;next} f&&/^[^[:space:]]/{exit} f&&/^[[:space:]]*use:/{sub(/^[[:space:]]*use:[[:space:]]*/,"");print;exit}' "$config_path" 2>/dev/null || true)"
    if [ "$sandbox_provider" = "ideer.community.aio_sandbox:AioSandboxProvider" ]; then
        sandbox_image="$(awk '/^sandbox:/{f=1;next} f&&/^[^[:space:]]/{exit} f&&/^[[:space:]]*image:/{sub(/^[[:space:]]*image:[[:space:]]*/,"");gsub(/"/,"");print;exit}' "$config_path" 2>/dev/null || true)"
        if [ -n "$sandbox_image" ] && [ "$sandbox_image" != "null" ] && ! docker image inspect "$sandbox_image" >/dev/null 2>&1; then
            warn "sandbox.image '${sandbox_image}' is not present in the local Docker daemon; sandboxed tools (bash, file writes) will fail until the image is loaded or sandbox.use is changed"
        fi
    fi
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

# On upgrade, env.intranet already exists with image tags from the previous
# bundle version.  Refresh them to the current bundle version so restart
# actually switches images; a value that does not look like a bundle image
# (e.g. a custom registry image) is left untouched.
refresh_image_tags() {
    [ -f "$ENV_FILE" ] || return 0
    local entry key value current
    for entry in \
        "IDEER_GATEWAY_IMAGE=ideer-gateway:$VERSION" \
        "IDEER_FRONTEND_IMAGE=ideer-frontend:$VERSION"; do
        key="${entry%%=*}"
        value="${entry#*=}"
        current="$(grep -E "^${key}=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
        if [ -z "$current" ]; then
            append_env_if_missing "$key" "$value"
        elif [ "$current" != "$value" ] && [[ "$current" == ideer-gateway:* || "$current" == ideer-frontend:* ]]; then
            log "refreshing $key: $current -> $value"
            run_cmd sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        fi
    done
}

seed_runtime() {
    run_cmd mkdir -p "$RUNTIME_DIR/data"

    seed_config
    patch_agents_api_enabled
    patch_officecli_mount
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

    refresh_image_tags

    patch_sandbox_image
}

# Incremental bundles do not ship the sandbox image (it is a stable retag of
# the upstream sandbox, so it never needs re-transferring between versions).
# When the versioned sandbox tag is missing after load, reuse a local
# ideer-sandbox:* tag so sandbox config patching still works.
ensure_sandbox_tag() {
    local image="ideer-sandbox:$VERSION"
    if docker image inspect "$image" >/dev/null 2>&1; then
        return 0
    fi
    local existing
    existing="$(docker images --format '{{.Repository}}:{{.Tag}}' | grep '^ideer-sandbox:' | grep -v '<none>' | head -1 || true)"
    [ -n "$existing" ] || return 0
    log "sandbox image $image not in this bundle; retagging local $existing"
    run_cmd docker tag "$existing" "$image"
    warn "reusing local $existing for $image; use a full bundle to update the sandbox image"
}

load_images() {
    if [ "$NO_LOAD" -eq 1 ]; then
        log "skipping docker load"
        return 0
    fi

    log "loading docker images..."
    run_cmd docker load -i "$IMAGES_TAR"
    ensure_sandbox_tag
}

# Remove ideer-gateway:* / ideer-frontend:* image tags older than the current
# version plus --keep-versions recent versions, so repeated upgrades do not
# grow the Docker daemon without bound.  The current version is always kept;
# nginx:alpine and ideer-sandbox:* are never touched (the sandbox tag shares
# its image with every version, so removing old tags frees no space).
prune_old_images() {
    # shellcheck disable=SC1090
    . "$ENV_FILE"

    local current_version=""
    local img
    img="$(grep -E '^IDEER_GATEWAY_IMAGE=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
    case "$img" in
        ideer-gateway:*) current_version="${img#ideer-gateway:}" ;;
    esac
    [ -n "$current_version" ] || {
        warn "cannot resolve the current bundle version from $ENV_FILE; keeping all images"
        return 0
    }

    local -a versions=()
    mapfile -t versions < <(docker images --format '{{.Repository}}:{{.Tag}}' | sed -n 's/^ideer-gateway://p' | sort -V || true)
    [ "${#versions[@]}" -gt 0 ] || {
        log "no ideer-gateway images found; nothing to prune"
        return 0
    }

    local -a keep_versions=()
    local i v
    keep_versions+=("$current_version")
    local added=0
    for ((i = ${#versions[@]} - 1; i >= 0; i--)); do
        v="${versions[$i]}"
        [ "$v" = "$current_version" ] && continue
        [ "$added" -ge "$KEEP_VERSIONS" ] && break
        keep_versions+=("$v")
        added=$((added + 1))
    done

    if [ "${#versions[@]}" -le 1 ]; then
        log "only the current version ($current_version) is present; nothing to prune"
        return 0
    fi

    local removed=0 repo
    for v in "${versions[@]}"; do
        if [[ " ${keep_versions[*]} " == *" $v "* ]]; then
            continue
        fi
        for repo in ideer-gateway ideer-frontend; do
            if docker image inspect "$repo:$v" >/dev/null 2>&1; then
                log "removing old image: $repo:$v"
                if ! run_cmd docker image rm "$repo:$v"; then
                    warn "failed to remove $repo:$v (may still be in use by a container)"
                fi
                removed=1
            fi
        done
    done
    if [ "$removed" -eq 1 ]; then
        log "image pruning complete; kept $(printf '%s, ' "${keep_versions[@]}" | sed 's/, $//')"
    else
        log "no old images to prune"
    fi
}

compose_cmd() {
    run_cmd docker compose -p ideer -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

# POST a JSON body and print the HTTP status code.  Uses curl when available
# and falls back to python3 so machines without curl can still bootstrap.
http_post_json() {
    local url="$1"
    local json="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -sS -o /dev/null -w '%{http_code}' -X POST "$url" \
            -H 'Content-Type: application/json' --data "$json"
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        python3 -c '
import json, sys, urllib.request
url, payload = sys.argv[1], sys.argv[2].encode()
req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=15):
        print(200)
except urllib.error.HTTPError as exc:
    print(exc.code)
' "$url" "$json"
        return 0
    fi
    die "curl or python3 is required to initialize the super admin"
}

# Create the first super admin account once the gateway is healthy.  The
# /initialize endpoint refuses with 409 when an admin already exists, so this
# is idempotent across re-runs.  Credentials default to the standard test
# account and can be overridden with IDEER_ADMIN_EMAIL / IDEER_ADMIN_PASSWORD.
initialize_super_admin() {
    local email="${IDEER_ADMIN_EMAIL:-super_admin@test.com}"
    local password="${IDEER_ADMIN_PASSWORD:-super_admin@test.com}"

    # shellcheck disable=SC1090
    . "$ENV_FILE"
    local port="${PORT:-2026}"

    log "initializing super admin account ($email)..."
    local status
    status="$(http_post_json \
        "http://127.0.0.1:${port}/api/v1/auth/initialize" \
        "{\"email\":\"${email}\",\"password\":\"${password}\"}")" || die "failed to reach the gateway for admin initialization"
    case "$status" in
        201) log "super admin account created" ;;
        409) log "super admin already exists; skipping" ;;
        *)
            die "admin initialization failed (HTTP $status)"
            ;;
    esac
}

# Resolve the active super admin user id from the runtime database.  Prints
# nothing when no admin exists yet (e.g. first boot before initialization).
find_super_admin_id() {
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    local db="${IDEER_HOME:-$RUNTIME_DIR/data}/data/ideer.db"
    [ -f "$db" ] || return 0
    python3 - "$db" <<'PY'
import sqlite3, sys
try:
    with sqlite3.connect(sys.argv[1]) as conn:
        row = conn.execute(
            "SELECT id FROM users_ext WHERE role='super_admin' AND disabled=0 LIMIT 1"
        ).fetchone()
except sqlite3.Error:
    row = None
print(row[0] if row else "")
PY
}

# Install the bundled agents (fault-zeroing, srs-writing), assign the bundled
# custom skills, and seed the fault-zeroing workflow as PRIVATE resources of
# the super admin.  Runs after the gateway is healthy and the admin exists
# because the per-user install and resource ownership live in the runtime
# database.  Skip each agent with IDEER_INSTALL_<NAME>=0.
install_admin_bundled_resources() {
    local resource_install_failed=0
    command -v python3 >/dev/null 2>&1 || {
        warn "python3 not found; skipping bundled resource install"
        return 1
    }

    require_file "$ENV_FILE"
    # shellcheck disable=SC1090
    . "$ENV_FILE"

    # The env file is the source of truth for the data dir: only trust the
    # IDEER_HOME it explicitly declares.  A pre-existing env file (e.g. from a
    # first boot before IDEER_HOME was added) must not inherit an unrelated
    # IDEER_HOME from the surrounding shell, which would relocate the agents.
    local runtime_home="$RUNTIME_DIR/data"
    if grep -qE '^IDEER_HOME=' "$ENV_FILE"; then
        runtime_home="${IDEER_HOME:-$runtime_home}"
    fi
    local config_path="${IDEER_CONFIG_PATH:-$RUNTIME_DIR/config.yaml}"
    require_file "$config_path"

    local admin_id
    admin_id="$(find_super_admin_id)"
    if [ -z "$admin_id" ]; then
        warn "no active super admin found in runtime DB; bundled resources cannot be initialized"
        return 1
    fi
    log "installing bundled resources for super admin $admin_id (public)..."

    # Older bundle versions auto-installed the bundled agents into the shared
    # directory (runtime/data/agents/<name>), which keeps them visible to every
    # user as read-only templates.  Once the per-user copy is in place,
    # remove a legacy shared copy when it still matches the bundle byte-for-byte;
    # a customized shared agent is left behind with a warning.
    cleanup_legacy_shared_agent() {
        local name="$1"
        local source_dir="$2"
        local shared_dir="$runtime_home/agents/$name"
        [ -d "$shared_dir" ] || return 0
        if ! diff -rq "$source_dir" "$shared_dir" >/dev/null 2>&1; then
            warn "legacy shared agent $shared_dir differs from the bundle; leaving it for manual review"
            return 0
        fi
        log "removing legacy shared agent copy: $shared_dir"
        run_cmd rm -rf "$shared_dir"
    }

    if [ "${IDEER_INSTALL_FAULT_ZEROING:-1}" = "0" ]; then
        log "skipping fault-zeroing agent install"
    elif [ -d "$SOURCE_DIR/resources/agents/fault-zeroing" ] && [ -f "$SOURCE_DIR/scripts/install_agent.py" ]; then
        log "installing bundled fault-zeroing agent for super admin (public)..."
        if ! run_cmd env IDEER_HOME="$runtime_home" IDEER_CONFIG_PATH="$config_path" \
            python3 "$SOURCE_DIR/scripts/install_agent.py" --agent fault-zeroing --owner super-admin
        then
            resource_install_failed=1
        fi
        cleanup_legacy_shared_agent fault-zeroing "$SOURCE_DIR/resources/agents/fault-zeroing"
    else
        warn "fault-zeroing agent source not found in bundle"
        resource_install_failed=1
    fi

    if [ "${IDEER_INSTALL_SRS_WRITING:-1}" = "0" ]; then
        log "skipping srs-writing agent install"
    elif [ -d "$SOURCE_DIR/resources/agents/srs-writing" ] && [ -f "$SOURCE_DIR/scripts/install_srs_writing_agent.py" ]; then
        log "installing bundled srs-writing agent for super admin (public)..."
        if ! run_cmd env IDEER_HOME="$runtime_home" IDEER_CONFIG_PATH="$config_path" \
            python3 "$SOURCE_DIR/scripts/install_srs_writing_agent.py" --owner super-admin; then
            warn "srs-writing agent install failed (see output above)"
            resource_install_failed=1
        fi
        cleanup_legacy_shared_agent srs-writing "$SOURCE_DIR/resources/agents/srs-writing"
    else
        warn "srs-writing agent source not found in bundle"
        resource_install_failed=1
    fi

    if [ ! -f "$SOURCE_DIR/scripts/seed_bundled_resources.py" ] \
        || [ ! -f "$SOURCE_DIR/bundled-resources.json" ]; then
        warn "canonical bundled resource seeder or manifest is missing"
        resource_install_failed=1
    elif ! docker container inspect ideer-gateway >/dev/null 2>&1; then
        warn "gateway container not running; cannot seed canonical bundled resources"
        resource_install_failed=1
    elif ! run_cmd docker cp "$SOURCE_DIR/scripts/seed_bundled_resources.py" ideer-gateway:/tmp/seed_bundled_resources.py \
        || ! run_cmd docker cp "$SOURCE_DIR/bundled-resources.json" ideer-gateway:/tmp/bundled-resources.json \
        || ! run_cmd docker compose -p ideer -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T gateway \
            sh -c 'cd /app/backend && PYTHONPATH=. uv run --no-sync python /tmp/seed_bundled_resources.py --manifest /tmp/bundled-resources.json --source-root /app --owner '"$admin_id"' --conflict-policy '"$BUNDLED_CONFLICT"; then
        warn "canonical bundled resource seeding failed"
        resource_install_failed=1
    fi

    return "$resource_install_failed"
}

# Seed the bundled fault-zeroing workflow into the workflow v2 store after the
# gateway is healthy (the DB only exists after the first boot).  Runs the
# repository's seed script inside the gateway container, so it needs no Python
# tooling on the host.  The workflow is recorded as a public resource owned by
# the active super admin (falling back to "system" when none exists).
# Idempotent; a missing or failed seed aborts deployment initialization.
seed_bundled_workflows() {
    [ -f "$SOURCE_DIR/resources/workflows/fault-zeroing.yaml" ] || return 1
    [ -f "$SOURCE_DIR/scripts/seed_fault_zeroing_workflow.py" ] || return 1

    if ! docker container inspect ideer-gateway >/dev/null 2>&1; then
        warn "gateway container not running; cannot seed bundled workflow"
        return 1
    fi

    local created_by="system"
    local admin_id
    admin_id="$(find_super_admin_id)"
    if [ -n "$admin_id" ]; then
        created_by="$admin_id"
    fi

    log "seeding bundled fault-zeroing workflow (owner: $created_by)..."
    if run_cmd docker cp "$SOURCE_DIR/resources/workflows/fault-zeroing.yaml" ideer-gateway:/tmp/fault-zeroing.yaml \
        && run_cmd docker cp "$SOURCE_DIR/scripts/seed_fault_zeroing_workflow.py" ideer-gateway:/tmp/seed_fault_zeroing_workflow.py \
        && run_cmd docker compose -p ideer -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T gateway \
            sh -c 'cd /app/backend && PYTHONPATH=. uv run --no-sync python /tmp/seed_fault_zeroing_workflow.py --workflow-path /tmp/fault-zeroing.yaml --created-by '"$created_by"; then
        log "bundled fault-zeroing workflow seeded"
    else
        warn "bundled workflow seed failed; run it manually after 'up' with:"
        warn "  docker compose -p ideer exec gateway sh -c 'cd /app/backend && PYTHONPATH=. uv run --no-sync python /tmp/seed_fault_zeroing_workflow.py --workflow-path /tmp/fault-zeroing.yaml --created-by '"$created_by"'"
        return 1
    fi
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

    die "$label health check failed: $url. Run './deploy-intranet.sh logs gateway', './deploy-intranet.sh logs workflow-worker', and './deploy-intranet.sh logs frontend' for details."
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
   ./deploy-intranet.sh logs workflow-worker
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
    prune-old)
        prepare_bundle
        prune_old_images
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
            initialize_super_admin
            if ! install_admin_bundled_resources; then
                die "public resource initialization failed"
            fi
            if ! seed_bundled_workflows; then
                die "bundled workflow initialization failed"
            fi
        fi
        if [ "$PRUNE_OLD" -eq 1 ]; then
            prune_old_images
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
            initialize_super_admin
            if ! install_admin_bundled_resources; then
                die "public resource initialization failed"
            fi
            if ! seed_bundled_workflows; then
                die "bundled workflow initialization failed"
            fi
        fi
        if [ "$PRUNE_OLD" -eq 1 ]; then
            prune_old_images
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
