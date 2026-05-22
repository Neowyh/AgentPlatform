#!/usr/bin/env bash
#
# run-local-services.sh - Start DeerFlow local services for browser validation.
#
# This launcher keeps Gateway and Frontend in tmux sessions, then starts nginx
# as the unified localhost:2026 entrypoint. It is intentionally small and
# avoids serve.sh's port-only readiness check because Next.js can be reachable
# before lsof reports a LISTEN socket in some local environments.

set -euo pipefail

REPO_ROOT="$(builtin cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd -P)"
cd "$REPO_ROOT"

GATEWAY_SESSION="deerflow-gateway"
FRONTEND_SESSION="deerflow-frontend"
NGINX_CONF="$REPO_ROOT/temp/nginx.local.runtime.conf"
NGINX_SOURCE_CONF="$REPO_ROOT/docker/nginx/nginx.local.conf"

usage() {
    cat <<'EOF'
Usage: scripts/run-local-services.sh [start|stop|restart|status|logs]

Commands:
  start     Start Gateway, Frontend, and nginx in the background (default)
  stop      Stop local DeerFlow services started by this script
  restart   Stop, then start
  status    Show service health and background sessions
  logs      Show recent Gateway, Frontend, and nginx logs

Open http://localhost:2026 after start succeeds.
EOF
}

ensure_tools() {
    for tool in tmux curl nginx uv pnpm; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            echo "Missing required command: $tool" >&2
            exit 1
        fi
    done
}

ensure_dirs() {
    mkdir -p logs temp/client_body_temp temp/proxy_temp temp/fastcgi_temp temp/uwsgi_temp temp/scgi_temp
}

render_nginx_conf() {
    python3 - "$NGINX_SOURCE_CONF" "$NGINX_CONF" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
needle = "http {\n"
injection = """http {
    client_body_temp_path temp/client_body_temp;
    proxy_temp_path temp/proxy_temp;
    fastcgi_temp_path temp/fastcgi_temp;
    uwsgi_temp_path temp/uwsgi_temp;
    scgi_temp_path temp/scgi_temp;
"""
if needle not in text:
    raise SystemExit(f"Could not find http block in {source}")
target.write_text(text.replace(needle, injection, 1), encoding="utf-8")
PY
}

tmux_has_session() {
    tmux has-session -t "$1" 2>/dev/null
}

tmux_start_or_restart() {
    local session="$1"
    local command="$2"

    if tmux_has_session "$session"; then
        tmux kill-session -t "$session"
    fi
    tmux new-session -d -s "$session" "$command"
}

wait_url() {
    local name="$1"
    local url="$2"
    local timeout="${3:-60}"
    local elapsed=0

    while ! curl -fsS "$url" >/dev/null 2>&1; do
        if [ "$elapsed" -ge "$timeout" ]; then
            echo ""
            echo "Failed to start $name after ${timeout}s: $url" >&2
            return 1
        fi
        printf "\r  Waiting for %s... %ds" "$name" "$elapsed"
        sleep 1
        elapsed=$((elapsed + 1))
    done
    printf "\r  %-60s\r" ""
    echo "OK $name"
}

stop_nginx() {
    nginx -c "$NGINX_CONF" -p "$REPO_ROOT" -s quit >/dev/null 2>&1 || true
    sleep 1
    if command -v lsof >/dev/null 2>&1; then
        local pids
        pids="$(lsof -ti :2026 2>/dev/null || true)"
        if [ -n "$pids" ]; then
            kill $pids >/dev/null 2>&1 || true
        fi
    fi
}

stop_services() {
    echo "Stopping DeerFlow local services..."
    stop_nginx
    tmux kill-session -t "$GATEWAY_SESSION" >/dev/null 2>&1 || true
    tmux kill-session -t "$FRONTEND_SESSION" >/dev/null 2>&1 || true
    echo "Stopped."
}

start_services() {
    ensure_tools
    ensure_dirs
    render_nginx_conf

    echo "Starting Gateway in tmux session: $GATEWAY_SESSION"
    tmux_start_or_restart "$GATEWAY_SESSION" \
        "cd '$REPO_ROOT/backend' && PYTHONPATH=. uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 > ../logs/gateway.log 2>&1"
    wait_url "Gateway" "http://localhost:8001/health" 60

    echo "Starting Frontend in tmux session: $FRONTEND_SESSION"
    tmux_start_or_restart "$FRONTEND_SESSION" \
        "cd '$REPO_ROOT/frontend' && pnpm run dev > ../logs/frontend.log 2>&1"
    wait_url "Frontend" "http://localhost:3000" 120

    echo "Starting nginx on http://localhost:2026"
    stop_nginx
    nginx -t -c "$NGINX_CONF" -p "$REPO_ROOT" >/dev/null
    nginx -c "$NGINX_CONF" -p "$REPO_ROOT"
    wait_url "Unified entrypoint" "http://localhost:2026/health" 30

    echo ""
    echo "DeerFlow is running: http://localhost:2026"
    echo "Logs: logs/gateway.log, logs/frontend.log, logs/nginx-error.log"
    echo "Stop: scripts/run-local-services.sh stop"
}

status_services() {
    echo "Sessions:"
    tmux list-sessions 2>/dev/null | grep -E "^(${GATEWAY_SESSION}|${FRONTEND_SESSION}):" || true
    echo ""
    echo "Health:"
    curl -fsS http://localhost:8001/health || true
    echo ""
    curl -fsS -I http://localhost:3000 | head -n 1 || true
    curl -fsS http://localhost:2026/health || true
    echo ""
}

show_logs() {
    echo "== Gateway =="
    tail -n 80 logs/gateway.log 2>/dev/null || true
    echo ""
    echo "== Frontend =="
    tail -n 80 logs/frontend.log 2>/dev/null || true
    echo ""
    echo "== nginx =="
    tail -n 80 logs/nginx-error.log 2>/dev/null || true
}

case "${1:-start}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        start_services
        ;;
    status)
        status_services
        ;;
    logs)
        show_logs
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        usage >&2
        exit 1
        ;;
esac
