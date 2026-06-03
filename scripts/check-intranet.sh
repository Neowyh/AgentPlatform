#!/usr/bin/env bash
# iDeer Intranet Deployment Pre-check
# Validates that all prerequisites for intranet deployment are met.

set -euo pipefail

ERRORS=0
WARNINGS=0

echo "=== iDeer Intranet Deployment Pre-check ==="
echo ""

# 1. Check Docker is available
echo -n "[1/8] Docker... "
if command -v docker &>/dev/null; then
    echo "OK ($(docker --version | head -1))"
else
    echo "MISSING"; ((ERRORS++))
fi

# 2. Check Docker Compose is available
echo -n "[2/8] Docker Compose... "
if docker compose version &>/dev/null 2>&1; then
    echo "OK"
else
    echo "MISSING"; ((ERRORS++))
fi

# 3. Check required Docker images are loaded
echo "[3/8] Docker images..."
REQUIRED_IMAGES=("ideer-frontend:latest" "ideer-gateway:latest" "nginx:alpine")
for img in "${REQUIRED_IMAGES[@]}"; do
    echo -n "  - $img... "
    if docker image inspect "$img" &>/dev/null; then
        echo "OK"
    else
        echo "MISSING"; ((WARNINGS++))
    fi
done

# 4. Check config.intranet.yaml exists
echo -n "[4/8] config.intranet.yaml... "
if [ -f "config.intranet.yaml" ]; then
    echo "OK"
else
    echo "MISSING (copy from config.intranet.yaml.example and customize)"; ((ERRORS++))
fi

# 5. Check .env.intranet exists
echo -n "[5/8] docker/.env.intranet... "
if [ -f "docker/.env.intranet" ]; then
    echo "OK"
else
    echo "MISSING (copy from docker/.env.intranet and customize)"; ((WARNINGS++))
fi

# 6. Check LLM endpoint is reachable (if configured)
echo -n "[6/8] LLM endpoint... "
if [ -n "${IDEER_LLM_ENDPOINT:-}" ]; then
    if curl -s --connect-timeout 3 "${IDEER_LLM_ENDPOINT}/models" >/dev/null 2>&1 || \
       curl -s --connect-timeout 3 "${IDEER_LLM_ENDPOINT}/v1/models" >/dev/null 2>&1; then
        echo "OK ($IDEER_LLM_ENDPOINT)"
    else
        echo "UNREACHABLE ($IDEER_LLM_ENDPOINT)"; ((WARNINGS++))
    fi
else
    echo "SKIPPED (set IDEER_LLM_ENDPOINT to check)"
fi

# 7. Check ports are available
echo "[7/8] Port availability..."
for port in 80 3000 8080; do
    echo -n "  - Port $port... "
    if ss -tlnp 2>/dev/null | grep -q ":${port} " || netstat -tlnp 2>/dev/null | grep -q ":${port} "; then
        echo "IN USE"; ((WARNINGS++))
    else
        echo "OK"
    fi
done

# 8. Check disk space
echo -n "[8/8] Disk space... "
AVAILABLE_GB=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE_GB" -ge 10 ]; then
    echo "OK (${AVAILABLE_GB}GB available)"
else
    echo "LOW (${AVAILABLE_GB}GB available, recommend 10GB+)"; ((WARNINGS++))
fi

echo ""
echo "=== Results ==="
echo "Errors: $ERRORS"
echo "Warnings: $WARNINGS"

if [ "$ERRORS" -gt 0 ]; then
    echo "FAILED: Please fix the errors above before deploying."
    exit 1
else
    echo "PASSED: Ready for intranet deployment."
    exit 0
fi
