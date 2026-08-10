#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/package-intranet-offline.sh [options]

Build iDeer runtime images and assemble an offline deployment bundle.

Options:
  --version <value>       Bundle version tag. Default: YYYYMMDD-<git short hash>
  --output-dir <path>     Output directory. Default: dist/intranet/ideer-<version>
  --platform <value>      Build platform. Default: linux/amd64
  --sandbox-image <value> Sandbox container image to bundle explicitly.
                          Retagged as ideer-sandbox:<version> inside the bundle.
  --no-sandbox            Skip bundling the sandbox image (the default).
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
    printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION=""
OUTPUT_DIR=""
PLATFORM="linux/amd64"
SANDBOX_IMAGE=""
NO_SANDBOX=1
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
        --sandbox-image)
            [ "$#" -ge 2 ] || die "--sandbox-image requires a value"
            SANDBOX_IMAGE="$2"
            NO_SANDBOX=0
            shift 2
            ;;
        --no-sandbox)
            NO_SANDBOX=1
            shift
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
    OUTPUT_DIR="$REPO_ROOT/dist/intranet/ideer-$VERSION"
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

GATEWAY_IMAGE="ideer-gateway:$VERSION"
FRONTEND_IMAGE="ideer-frontend:$VERSION"
NGINX_IMAGE="nginx:alpine"
BUNDLED_SANDBOX_TAG="ideer-sandbox:$VERSION"
INCLUDE_SANDBOX=0
SOURCE_TAR="$OUTPUT_DIR/ideer-source-$VERSION.tar.gz"
IMAGES_TAR="$OUTPUT_DIR/ideer-images-$VERSION.tar"
MANIFEST_FILE="$OUTPUT_DIR/MANIFEST.txt"
SHA_FILE="$OUTPUT_DIR/SHA256SUMS"
GUIDE_FILE="$REPO_ROOT/docs/deployment/禁公网内网离线部署作业指导书.md"
DEPLOY_SCRIPT_FILE="$REPO_ROOT/scripts/deploy-intranet.sh"
CHECK_SCRIPT_FILE="$REPO_ROOT/scripts/check-intranet.sh"
GUIDE_BASENAME="$(basename "$GUIDE_FILE")"
DEPLOY_BASENAME="$(basename "$DEPLOY_SCRIPT_FILE")"
CHECK_BASENAME="$(basename "$CHECK_SCRIPT_FILE")"

log "output: $OUTPUT_DIR"
log "version: $VERSION"
log "platform: $PLATFORM"
echo ""

BUILD_CACHE_ARGS=()
if [ "$NO_CACHE" -eq 1 ]; then
    BUILD_CACHE_ARGS+=(--no-cache)
fi

log "[1/7] building gateway image..."
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

log "[2/7] building frontend image..."
docker build \
    "${BUILD_CACHE_ARGS[@]}" \
    --platform "$PLATFORM" \
    --build-arg PNPM_STORE_PATH="${PNPM_STORE_PATH:-/root/.local/share/pnpm/store}" \
    --build-arg NPM_REGISTRY="${NPM_REGISTRY:-}" \
    -f "$REPO_ROOT/frontend/Dockerfile" \
    --target prod \
    -t "$FRONTEND_IMAGE" \
    "$REPO_ROOT"

log "[3/7] pulling nginx image..."
docker pull "$NGINX_IMAGE"

log "[4/7] preparing sandbox image..."
if [ "$NO_SANDBOX" -eq 1 ]; then
    log "  sandbox image disabled (--no-sandbox); bundle will not include a sandbox image"
else
    log "  pulling: $SANDBOX_IMAGE"
    docker pull "$SANDBOX_IMAGE"
    local_arch="$(docker image inspect "$SANDBOX_IMAGE" --format '{{.Architecture}}' 2>/dev/null || true)"
    expected_arch="${PLATFORM#linux/}"
    if [ -n "$local_arch" ] && [ -n "$expected_arch" ] && [ "$local_arch" != "$expected_arch" ]; then
        warn "sandbox image architecture '$local_arch' does not match --platform '$PLATFORM'; target machines must load it on $local_arch hosts"
    fi
    log "  tagging as $BUNDLED_SANDBOX_TAG"
    docker tag "$SANDBOX_IMAGE" "$BUNDLED_SANDBOX_TAG"
    INCLUDE_SANDBOX=1
fi

log "[5/7] saving docker images..."
IMAGES_TO_SAVE=("$GATEWAY_IMAGE" "$FRONTEND_IMAGE" "$NGINX_IMAGE")
if [ "$INCLUDE_SANDBOX" -eq 1 ]; then
    IMAGES_TO_SAVE+=("$BUNDLED_SANDBOX_TAG")
fi
docker save -o "$IMAGES_TAR" "${IMAGES_TO_SAVE[@]}"

log "[6/7] packing source archive..."
tar \
    -C "$REPO_ROOT" \
    --exclude='.git' \
    --exclude='dist' \
    --exclude='backend/.venv' \
    --exclude='backend/.ideer' \
    --exclude='backend/.pytest_cache' \
    --exclude='backend/.ruff_cache' \
    --exclude='backend/__pycache__' \
    --exclude='**/__pycache__' \
    --exclude='*.pyc' \
    --exclude='frontend/node_modules' \
    --exclude='frontend/.next' \
    --exclude='frontend/.cache' \
    --exclude='frontend/.env' \
    --exclude='frontend/test-results' \
    --exclude='frontend/playwright-report' \
    --exclude='frontend/tsconfig.tsbuildinfo' \
    --exclude='node_modules' \
    --exclude='logs' \
    --exclude='*.log' \
    -czf "$SOURCE_TAR" \
    .env.example \
    Makefile \
    README.md \
    backend \
    config.example.yaml \
    config.intranet.yaml \
    docker \
    docs \
    extensions_config.example.json \
    frontend \
    scripts \
    skills \
    vendor \
    workflows

log "[7/7] assembling bundle..."
cp "$GUIDE_FILE" "$OUTPUT_DIR/$GUIDE_BASENAME"
cp "$DEPLOY_SCRIPT_FILE" "$OUTPUT_DIR/$DEPLOY_BASENAME"
cp "$CHECK_SCRIPT_FILE" "$OUTPUT_DIR/$CHECK_BASENAME"

# Copy config files if they exist
if [ -f "$REPO_ROOT/config.intranet.yaml" ]; then
    cp "$REPO_ROOT/config.intranet.yaml" "$OUTPUT_DIR/config.intranet.yaml"
fi
if [ -f "$REPO_ROOT/docker/.env.intranet" ]; then
    cp "$REPO_ROOT/docker/.env.intranet" "$OUTPUT_DIR/.env.intranet"
fi

# Collect image digests for the manifest
GATEWAY_DIGEST="$(docker image inspect "$GATEWAY_IMAGE" --format '{{.Id}}' 2>/dev/null | cut -c8-19 || echo 'unknown')"
FRONTEND_DIGEST="$(docker image inspect "$FRONTEND_IMAGE" --format '{{.Id}}' 2>/dev/null | cut -c8-19 || echo 'unknown')"
NGINX_DIGEST="$(docker image inspect "$NGINX_IMAGE" --format '{{.Id}}' 2>/dev/null | cut -c8-19 || echo 'unknown')"
if [ "$INCLUDE_SANDBOX" -eq 1 ]; then
    SANDBOX_DIGEST="$(docker image inspect "$BUNDLED_SANDBOX_TAG" --format '{{.Id}}' 2>/dev/null | cut -c8-19 || echo 'unknown')"
    SANDBOX_SOURCE_NOTE=" (source: $SANDBOX_IMAGE)"
    SANDBOX_SOURCE_LINE="  - Source image for the sandbox: $SANDBOX_IMAGE"
else
    SANDBOX_DIGEST="not bundled"
    SANDBOX_SOURCE_NOTE=" (not bundled; deployment must supply a sandbox image or use a local provider)"
    SANDBOX_SOURCE_LINE=""
fi

cat > "$MANIFEST_FILE" <<EOF
iDeer Intranet Offline Bundle
=============================
Version: $VERSION
Platform: $PLATFORM
Created at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Git commit: $(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo 'unknown')

Docker Images:
  - $GATEWAY_IMAGE (digest: $GATEWAY_DIGEST)
  - $FRONTEND_IMAGE (digest: $FRONTEND_DIGEST)
  - $NGINX_IMAGE (digest: $NGINX_DIGEST)
  - $BUNDLED_SANDBOX_TAG (digest: $SANDBOX_DIGEST)$SANDBOX_SOURCE_NOTE

Files:
  - $(basename "$IMAGES_TAR")        (Docker images archive)
  - $(basename "$SOURCE_TAR")       (Source code archive)
  - $GUIDE_BASENAME (Deployment guide)
  - $DEPLOY_BASENAME  (Deploy script)
  - $CHECK_BASENAME  (Pre-check script)
  - config.intranet.yaml  (Intranet config template)
  - .env.intranet         (Intranet environment template)
  - $(basename "$MANIFEST_FILE")        (This manifest)
  - $(basename "$SHA_FILE")          (SHA256 checksums)

Deployment Steps:
  1. Copy this entire bundle to the target intranet machine
  2. Run: ./check-intranet.sh     (verify prerequisites)
  3. Run: ./deploy-intranet.sh up (deploy and start services)
  4. Access http://localhost:2026 (or the configured port)

Notes:
  - deploy-intranet.sh prepare automatically rewrites sandbox.image in
    runtime/config.yaml to $BUNDLED_SANDBOX_TAG when the sandbox image is
    bundled. No manual sandbox configuration is required.
  - When the sandbox image is not bundled, either load a sandbox image
    manually and set sandbox.image to a locally present name, or switch
    sandbox.use to a provider that needs no image (local).
$SANDBOX_SOURCE_LINE
For details, see the deployment guide included in this bundle.
EOF

(cd "$OUTPUT_DIR" && sha256sum \
    "$(basename "$IMAGES_TAR")" \
    "$(basename "$SOURCE_TAR")" \
    "$GUIDE_BASENAME" \
    "$DEPLOY_BASENAME" \
    "$CHECK_BASENAME" \
    "$(basename "$MANIFEST_FILE")" \
    > "$(basename "$SHA_FILE")")

echo ""
log "=== Bundle Complete ==="
log "images tar:    $IMAGES_TAR"
log "source tar:    $SOURCE_TAR"
log "guide:         $OUTPUT_DIR/$GUIDE_BASENAME"
log "deploy script: $OUTPUT_DIR/$DEPLOY_BASENAME"
log "check script:  $OUTPUT_DIR/$CHECK_BASENAME"
log "manifest:      $MANIFEST_FILE"
log "sha256:        $SHA_FILE"
echo ""
log "Bundle size: $(du -sh "$OUTPUT_DIR" | awk '{print $1}')"
