#!/usr/bin/env bash
# Frontend entry-parity gate for upstream merges.
#
# Verifies that every entry the pre-merge baseline exposed is still reachable:
#   1. route files  — every baseline page route exists at HEAD
#   2. visible nav  — every baseline sidebar link still resolves (link OR an
#                     explicit allow-list entry in BASELINE_NAV_REMOVALS)
#   3. i18n labels  — sidebar translation keys survived
#   4. API orphans  — frontend /api calls resolve to real FastAPI routes
#                     (dumped from create_app(), the authoritative source)
#
# Usage: bash scripts/check-frontend-entry-parity.sh [BASE_REF] [HEAD_REF]
#        defaults: BASE_REF=dbb2a813 (pre-convergence develop), HEAD_REF=HEAD
# Exit 0 = parity holds; nonzero = entries were lost (see printed report).
set -euo pipefail

BASE_REF="${1:-dbb2a813}"
HEAD_REF="${2:-HEAD}"
fail=0

route_entries() {
    git ls-tree -r --name-only "$1" -- frontend/src/app |
        grep "page.tsx$" | sed -e 's|^frontend/src/app/||' -e 's|/page\.tsx$||'
}

echo "── 1. route-file parity ──"
lost_routes=$(comm -23 <(route_entries "$BASE_REF" | sort) <(route_entries "$HEAD_REF" | sort) || true)
if [ -n "$lost_routes" ]; then
    echo "  LOST ROUTES:"
    echo "$lost_routes" | sed 's/^/    /'
    fail=1
else
    echo "  OK: every baseline page route exists at HEAD"
fi

echo "── 2. visible navigation parity ──"
nav_href() {
    local f
    for f in workspace-nav-chat-list.tsx workspace-nav-menu.tsx; do
        git show "$1:frontend/src/components/workspace/$f" 2>/dev/null |
            grep -oE 'href="(/[^"$]+)"' | cut -d'"' -f2
    done | sort -u
}
baseline_nav=$(nav_href "$BASE_REF")
head_nav=$(nav_href "$HEAD_REF")
lost_nav=$(comm -23 <(printf '%s\n' "$baseline_nav") <(printf '%s\n' "$head_nav") || true)
if [ -n "$lost_nav" ]; then
    real_lost=""
    while IFS= read -r href; do
        [ -z "$href" ] && continue
        if printf '%s' "${BASELINE_NAV_REMOVALS:-}" | grep -qxF "$href"; then
            echo "  allowed removal: $href"
        else
            real_lost="${real_lost}${href}\n"
        fi
    done <<< "$lost_nav"
    if [ -n "$real_lost" ]; then
        echo "  LOST NAV LINKS (baseline sidebar link absent at HEAD):"
        printf "$real_lost" | sed 's/^/    /'
        echo "  → restore the link, or add the href to BASELINE_NAV_REMOVALS"
        echo "    when the removal is an explicit product decision."
        fail=1
    fi
else
    echo "  OK: every baseline sidebar link still present"
fi

echo "── 3. i18n sidebar keys ──"
sidebar_keys() {
    git show "$1:frontend/src/core/i18n/locales/zh-CN.ts" 2>/dev/null |
        sed -n '/^  sidebar: {/,/^  },/p' | grep -oE '^    [a-z]+:' | tr -d ' :' | sort
}
lost_keys=$(comm -23 <(sidebar_keys "$BASE_REF") <(sidebar_keys "$HEAD_REF") || true)
if [ -n "$lost_keys" ]; then
    echo "  LOST i18n KEYS: $lost_keys"
    fail=1
else
    echo "  OK: no sidebar i18n key lost"
fi

echo "── 4. API orphan sweep ──"
# Authoritative mounted-route dump: the real FastAPI app, not regex guesses.
REPO_ROOT="$(git rev-parse --show-toplevel)"
CACHE="$REPO_ROOT/.entry-parity-routes.txt"
mounted=""
if [ ! -s "$CACHE" ]; then
    (cd "$REPO_ROOT/backend" && uv run python - <<'PY'
from app.gateway.app import create_app

app = create_app()
for route in app.routes:
    path = getattr(route, "path", "")
    if path.startswith("/api"):
        print(path)
PY
    ) > "$CACHE" || { rm -f "$CACHE"; echo "  WARN: route dump failed, skipping API orphan check"; }
fi
[ -s "$CACHE" ] && mounted=$(sort -u "$CACHE")
frontend_calls=$(git grep -ohE '"/api/[a-z0-9/_-]+"' "$HEAD_REF" -- frontend/src |
    tr -d '"' | sed -E 's|/[^/]+$||' | sort -u)
orphans=""
while IFS= read -r family; do
    [ -z "$family" ] && continue
    hit=0
    while IFS= read -r bp; do
        [ -z "$bp" ] && continue
        case "$bp" in
            "$family"|"$family"/*) hit=1; break ;;
            "$family"*) case "$bp" in "$family"*) hit=1; break;; esac ;;
        esac
        case "$family" in "$bp"/*) hit=1; break ;; esac
    done <<< "$mounted"
    [ "$hit" -eq 0 ] && orphans="${orphans}${family}\n"
done <<< "$frontend_calls"
if [ -n "$orphans" ]; then
    echo "  ORPHAN API CALL FAMILIES (frontend calls, no mounted backend route):"
    printf "$orphans" | sort -u | sed 's/^/    /'
    echo "  → mount the router in app/gateway/app.py, or gate the caller."
    fail=1
else
    echo "  OK: no orphan frontend API calls"
fi

echo ""
if [ "$fail" -eq 0 ]; then
    echo "ENTRY-PARITY: PASSED"
else
    echo "ENTRY-PARITY: FAILED (see report above)"
fi
exit "$fail"
