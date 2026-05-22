#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/package-intranet-offline.sh [options]

Build DeerFlow runtime images and assemble an offline deployment bundle.

Options:
  --version <value>       Bundle version tag. Default: YYYYMMDD-<git short hash>
  --output-dir <path>     Output directory. Default: dist/intranet/deer-flow-<version>
  --platform <value>      Build platform. Default: linux/amd64
  --force                 Remove the output directory if it already exists
  --no-cache              Rebuild Docker images without using cache
  --require-clean         Fail if the git worktree contains uncommitted changes
  --help                  Show this help text
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
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION=""
OUTPUT_DIR=""
PLATFORM="linux/amd64"
FORCE=0
NO_CACHE=0
REQUIRE_CLEAN=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --version)
            [ "$#" -ge 2 ] || die "--version requires a value"
            VERSION="$2"
            shift 2
            ;;
        --output-dir)
            [ "$#" -ge 2 ] || die "--output-dir requires a value"
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --platform)
            [ "$#" -ge 2 ] || die "--platform requires a value"
            PLATFORM="$2"
            shift 2
            ;;
        --force)
            FORCE=1
            shift
            ;;
        --no-cache)
            NO_CACHE=1
            shift
            ;;
        --require-clean)
            REQUIRE_CLEAN=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

if [ -z "$VERSION" ]; then
    if git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        VERSION="$(date +%Y%m%d)-$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
    else
        VERSION="$(date +%Y%m%d)-manual"
    fi
fi

if [ -z "$OUTPUT_DIR" ]; then
    OUTPUT_DIR="$REPO_ROOT/dist/intranet/deer-flow-$VERSION"
fi

GIT_AVAILABLE=0
if git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    GIT_AVAILABLE=1
fi

if [ "$REQUIRE_CLEAN" -eq 1 ] && [ "$GIT_AVAILABLE" -eq 1 ]; then
    if [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
        die "git worktree is not clean; rerun without --require-clean or clean the tree first"
    fi
fi

if ! command -v docker >/dev/null 2>&1; then
    die "docker is required"
fi

if ! docker compose version >/dev/null 2>&1; then
    die "docker compose v2 is required"
fi

if ! docker info >/dev/null 2>&1; then
    cat >&2 <<'EOF'
error: cannot connect to the Docker daemon.

The current user cannot access /var/run/docker.sock, or the Docker daemon is not running.

Fix options:
  1. Start Docker, then retry:
       sudo systemctl start docker

  2. Grant the current user Docker access, then log out and log back in:
       sudo usermod -aG docker "$USER"

  3. For a one-off build, run this packaging script with sudo:
       sudo -E scripts/package-intranet-offline.sh --version <version> --force

Avoid chmod 666 /var/run/docker.sock on shared machines; it grants broad host-level access.
EOF
    exit 1
fi

if [ -e "$OUTPUT_DIR" ]; then
    if [ "$FORCE" -ne 1 ]; then
        die "output directory already exists: $OUTPUT_DIR (use --force to overwrite)"
    fi
    rm -rf "$OUTPUT_DIR"
fi

mkdir -p "$OUTPUT_DIR"

GATEWAY_IMAGE="deer-flow-gateway:$VERSION"
FRONTEND_IMAGE="deer-flow-frontend:$VERSION"
NGINX_IMAGE="nginx:alpine"
SOURCE_TAR="$OUTPUT_DIR/deer-flow-source-$VERSION.tar.gz"
IMAGES_TAR="$OUTPUT_DIR/deer-flow-images-$VERSION.tar"
COMPOSE_FILE="$OUTPUT_DIR/docker-compose.intranet.yaml"
ENV_EXAMPLE="$OUTPUT_DIR/env.intranet.example"
MANIFEST_FILE="$OUTPUT_DIR/MANIFEST.txt"
SHA_FILE="$OUTPUT_DIR/SHA256SUMS"
SOURCE_COMPOSE_FILE="$REPO_ROOT/docker/docker-compose.intranet.yaml"
GUIDE_FILE="$REPO_ROOT/docs/deployment/禁公网内网离线部署作业指导书.md"
DEPLOY_SCRIPT_FILE="$REPO_ROOT/scripts/deploy-intranet.sh"
GUIDE_BASENAME="$(basename "$GUIDE_FILE")"
DEPLOY_BASENAME="$(basename "$DEPLOY_SCRIPT_FILE")"

log "output: $OUTPUT_DIR"
log "version: $VERSION"
log "platform: $PLATFORM"

BUILD_CACHE_ARGS=()
if [ "$NO_CACHE" -eq 1 ]; then
    BUILD_CACHE_ARGS+=(--no-cache)
fi

log "building gateway image..."
docker build \
    "${BUILD_CACHE_ARGS[@]}" \
    --platform "$PLATFORM" \
    --build-arg UV_IMAGE="${UV_IMAGE:-ghcr.io/astral-sh/uv:0.7.20}" \
    --build-arg UV_INDEX_URL="${UV_INDEX_URL:-https://pypi.org/simple}" \
    --build-arg UV_EXTRAS="${UV_EXTRAS:-}" \
    --build-arg APT_MIRROR="${APT_MIRROR:-}" \
    -f "$REPO_ROOT/backend/Dockerfile" \
    -t "$GATEWAY_IMAGE" \
    "$REPO_ROOT"

log "building frontend image..."
docker build \
    "${BUILD_CACHE_ARGS[@]}" \
    --platform "$PLATFORM" \
    --build-arg PNPM_STORE_PATH="${PNPM_STORE_PATH:-/root/.local/share/pnpm/store}" \
    --build-arg NPM_REGISTRY="${NPM_REGISTRY:-}" \
    -f "$REPO_ROOT/frontend/Dockerfile" \
    --target prod \
    -t "$FRONTEND_IMAGE" \
    "$REPO_ROOT"

log "pulling nginx image..."
docker pull "$NGINX_IMAGE"

log "saving images..."
docker save -o "$IMAGES_TAR" "$GATEWAY_IMAGE" "$FRONTEND_IMAGE" "$NGINX_IMAGE"

log "packing source archive..."
tar \
    -C "$REPO_ROOT" \
    --exclude='.git' \
    --exclude='dist' \
    --exclude='backend/.venv' \
    --exclude='backend/.deer-flow' \
    --exclude='backend/.pytest_cache' \
    --exclude='backend/__pycache__' \
    --exclude='frontend/node_modules' \
    --exclude='frontend/.next' \
    --exclude='frontend/.cache' \
    --exclude='node_modules' \
    --exclude='logs' \
    --exclude='*.log' \
    -czf "$SOURCE_TAR" \
    Makefile \
    README.md \
    backend \
    config.example.yaml \
    docker \
    docs \
    extensions_config.example.json \
    frontend \
    scripts \
    skills

cp "$SOURCE_COMPOSE_FILE" "$COMPOSE_FILE"
cp "$GUIDE_FILE" "$OUTPUT_DIR/$GUIDE_BASENAME"
cp "$DEPLOY_SCRIPT_FILE" "$OUTPUT_DIR/$DEPLOY_BASENAME"

cat > "$ENV_EXAMPLE" <<EOF
# Copy this file to env.intranet and update the values for your environment.
PORT=2026
DEER_FLOW_HOME=/opt/deer-flow/runtime/data
DEER_FLOW_CONFIG_PATH=/opt/deer-flow/runtime/config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=/opt/deer-flow/runtime/extensions_config.json
DEER_FLOW_REPO_ROOT=/opt/deer-flow/source
DEER_FLOW_ENV_FILE=/opt/deer-flow/runtime/.env
DEER_FLOW_FRONTEND_ENV_FILE=/opt/deer-flow/runtime/frontend.env
DEER_FLOW_DOCKER_SOCKET=/var/run/docker.sock
BETTER_AUTH_SECRET=replace-with-a-fixed-secret
DEER_FLOW_GATEWAY_IMAGE=${GATEWAY_IMAGE}
DEER_FLOW_FRONTEND_IMAGE=${FRONTEND_IMAGE}
NGINX_IMAGE=${NGINX_IMAGE}
EOF

cat > "$MANIFEST_FILE" <<EOF
DeerFlow offline bundle
Version: $VERSION
Platform: $PLATFORM
Created at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

Files:
- $(basename "$IMAGES_TAR")
- $(basename "$SOURCE_TAR")
- $(basename "$COMPOSE_FILE")
- $(basename "$ENV_EXAMPLE")
- $GUIDE_BASENAME
- $DEPLOY_BASENAME
- $(basename "$MANIFEST_FILE")
- $(basename "$SHA_FILE")
EOF

(cd "$OUTPUT_DIR" && sha256sum "$(basename "$IMAGES_TAR")" "$(basename "$SOURCE_TAR")" "$(basename "$COMPOSE_FILE")" "$(basename "$ENV_EXAMPLE")" "$GUIDE_BASENAME" "$DEPLOY_BASENAME" "$(basename "$MANIFEST_FILE")" > "$(basename "$SHA_FILE")")

log "done"
log "images tar: $IMAGES_TAR"
log "source tar:  $SOURCE_TAR"
log "compose:     $COMPOSE_FILE"
log "env sample:  $ENV_EXAMPLE"
log "guide:       $OUTPUT_DIR/$GUIDE_BASENAME"
log "deploy:      $OUTPUT_DIR/$DEPLOY_BASENAME"
log "sha256:      $SHA_FILE"
