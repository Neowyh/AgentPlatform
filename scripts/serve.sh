#!/usr/bin/env bash
#
# serve.sh — Unified iDeer service launcher
#
# Usage:
#   ./scripts/serve.sh [--dev|--prod] [--daemon] [--stop|--restart]
#
# Modes:
#   --dev       Development mode with hot-reload (default)
#   --prod      Production mode, pre-built frontend, no hot-reload
#   --daemon    Run all services in background (nohup), exit after startup
#
# Actions:
#   --skip-install  Skip dependency installation (faster restart)
#   --stop      Stop all running services and exit
#   --restart   Stop all services, then start with the given mode flags
#
# Examples:
#   ./scripts/serve.sh --dev                 # Gateway + workflow worker, hot reload
#   ./scripts/serve.sh --prod                # Gateway + workflow worker, production
#   ./scripts/serve.sh --dev --daemon        # Gateway + workflow worker, background
#   ./scripts/serve.sh --stop                # Stop all services
#   ./scripts/serve.sh --restart --dev       # Restart dev services
#
# Must be run from the repo root directory.

set -e

REPO_ROOT="$(builtin cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd -P)"
cd "$REPO_ROOT"

WORKFLOW_WORKER_PID_FILE="$REPO_ROOT/logs/workflow-worker.pid"

# ── Load .env ────────────────────────────────────────────────────────────────

if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

# ── Argument parsing ─────────────────────────────────────────────────────────

DEV_MODE=true
DAEMON_MODE=false
SKIP_INSTALL=false
ACTION="start"   # start | stop | restart

for arg in "$@"; do
    case "$arg" in
        --dev)     DEV_MODE=true ;;
        --prod)    DEV_MODE=false ;;
        --daemon)  DAEMON_MODE=true ;;
        --skip-install) SKIP_INSTALL=true ;;
        --stop)    ACTION="stop" ;;
        --restart) ACTION="restart" ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--dev|--prod] [--daemon] [--skip-install] [--stop|--restart]"
            exit 1
            ;;
    esac
done

# ── Stop helper ──────────────────────────────────────────────────────────────

_is_repo_pid() {
    local pid=$1
    # 方法1：通过 lsof 检查进程打开的文件
    if lsof -p "$pid" 2>/dev/null | grep -qF "$REPO_ROOT"; then
        return 0
    fi
    # 方法2：通过 /proc 检查进程工作目录（Linux）
    if [ -d "/proc/$pid/cwd" ]; then
        local cwd
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null)
        if [[ "$cwd" == "$REPO_ROOT"* ]]; then
            return 0
        fi
    fi
    # 方法3：通过 ps 检查进程命令行
    if ps -p "$pid" -o args= 2>/dev/null | grep -qF "$REPO_ROOT"; then
        return 0
    fi
    return 1
}

_kill_repo_processes() {
    local pattern=$1
    local pid
    local pids=""

    while IFS= read -r pid; do
        if [ -n "$pid" ] && _is_repo_pid "$pid"; then
            case " $pids " in
                *" $pid "*) ;;
                *) pids="$pids $pid" ;;
            esac
        fi
    done < <(pgrep -f "$pattern" 2>/dev/null || true)

    if [ -n "$pids" ]; then
        kill $pids 2>/dev/null || true
    fi
}

_kill_repo_port() {
    local port=$1
    local pid
    local pids=""

    while IFS= read -r pid; do
        if [ -n "$pid" ] && _is_repo_pid "$pid"; then
            case " $pids " in
                *" $pid "*) ;;
                *) pids="$pids $pid" ;;
            esac
        fi
    done < <(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)

    if [ -n "$pids" ]; then
        # 优雅退出：先 SIGTERM，超时后 SIGKILL
        kill $pids 2>/dev/null || true
        sleep 2
        # 检查是否还有存活的进程
        local alive=""
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                alive="$alive $pid"
            fi
        done
        if [ -n "$alive" ]; then
            kill -9 $alive 2>/dev/null || true
        fi
    fi
}

_is_port_listening() {
    local port=$1

    if command -v lsof >/dev/null 2>&1; then
        if lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
            return 0
        fi
    fi

    if command -v ss >/dev/null 2>&1; then
        if ss -ltn "( sport = :$port )" 2>/dev/null | tail -n +2 | grep -q .; then
            return 0
        fi
    fi

    if command -v netstat >/dev/null 2>&1; then
        if netstat -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|[.:])${port}$"; then
            return 0
        fi
    fi

    return 1
}

_is_repo_nginx_pid() {
    local pid=$1
    local command
    local args

    command=$(ps -p "$pid" -o comm= 2>/dev/null) || return 1
    case "$command" in
        nginx|*/nginx) ;;
        *) return 1 ;;
    esac

    args=$(ps -p "$pid" -o args= 2>/dev/null) || return 1
    case "$args" in
        *"$REPO_ROOT/docker/nginx/nginx.local.conf"*|*"$REPO_ROOT"*) return 0 ;;
    esac

    _is_repo_pid "$pid"
}

_kill_repo_nginx() {
    local pid
    local pids=""

    if [ -f "$REPO_ROOT/logs/nginx.pid" ]; then
        read -r pid < "$REPO_ROOT/logs/nginx.pid" || true
        if [ -n "$pid" ] && _is_repo_nginx_pid "$pid"; then
            pids="$pids $pid"
        fi
    fi

    while IFS= read -r pid; do
        if [ -n "$pid" ] && _is_repo_nginx_pid "$pid"; then
            case " $pids " in
                *" $pid "*) ;;
                *) pids="$pids $pid" ;;
            esac
        fi
    done < <(pgrep -f nginx 2>/dev/null || true)

    if [ -n "$pids" ]; then
        kill -9 $pids 2>/dev/null || true
    fi
}

stop_all() {
    echo "Stopping all services..."
    
    # 检查是否有本仓库的服务在运行
    local has_services=false
    
    # 检查 workflow worker PID 文件
    if [ -f "$WORKFLOW_WORKER_PID_FILE" ]; then
        local worker_pid
        worker_pid=$(cat "$WORKFLOW_WORKER_PID_FILE")
        if [ -n "$worker_pid" ] && kill -0 "$worker_pid" 2>/dev/null; then
            has_services=true
        fi
    fi
    
    # 检查端口是否有服务在监听
    if _is_port_listening 8001 || _is_port_listening 3000 || _is_port_listening 2026; then
        has_services=true
    fi
    
    if [ "$has_services" = false ]; then
        echo "  No services running, skipping cleanup."
        return 0
    fi
    
    if [ -f "$WORKFLOW_WORKER_PID_FILE" ]; then
        worker_pid=$(cat "$WORKFLOW_WORKER_PID_FILE")
        if [ -n "$worker_pid" ] && kill -0 "$worker_pid" 2>/dev/null && _is_repo_pid "$worker_pid"; then
            kill "$worker_pid" 2>/dev/null || true
        fi
        rm -f "$WORKFLOW_WORKER_PID_FILE"
    fi
    _kill_repo_processes "python -m app.workflow_worker"
    _kill_repo_processes "uvicorn app.gateway.app:app"
    _kill_repo_processes "next dev"
    _kill_repo_processes "next start"
    _kill_repo_processes "next-server (v"
    nginx -c "$REPO_ROOT/docker/nginx/nginx.local.conf" -p "$REPO_ROOT" -s quit 2>/dev/null || true
    sleep 1
    _kill_repo_nginx
    # Force-kill any survivors still holding the service ports
    _kill_repo_port 8001
    _kill_repo_port 3000
    ./scripts/cleanup-containers.sh ideer-sandbox 2>/dev/null || true
    echo "✓ All services stopped"
}

# ── Action routing ───────────────────────────────────────────────────────────

if [ "$ACTION" = "stop" ]; then
    stop_all
    exit 0
fi

ALREADY_STOPPED=false
if [ "$ACTION" = "restart" ]; then
    stop_all
    sleep 1
    ALREADY_STOPPED=true
fi

# Mode label for banner
if $DEV_MODE; then
    MODE_LABEL="DEV (Gateway + workflow worker, hot-reload enabled)"
else
    MODE_LABEL="PROD (Gateway + workflow worker, optimized)"
fi

if $DAEMON_MODE; then
    MODE_LABEL="$MODE_LABEL [daemon]"
fi

# Frontend command
if $DEV_MODE; then
    FRONTEND_CMD="pnpm run dev"
else
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="python"
    else
        echo "Python is required to generate BETTER_AUTH_SECRET."
        exit 1
    fi
    FRONTEND_CMD="env BETTER_AUTH_SECRET=$($PYTHON_BIN -c 'import secrets; print(secrets.token_hex(16))') pnpm run preview"
fi

# Extra flags for uvicorn
if $DEV_MODE && ! $DAEMON_MODE; then
    GATEWAY_EXTRA_FLAGS="--reload --reload-include='*.yaml' --reload-include='.env' --reload-exclude='*.pyc' --reload-exclude='__pycache__' --reload-exclude='sandbox/' --reload-exclude='.ideer/'"
else
    GATEWAY_EXTRA_FLAGS=""
fi

# ── Stop existing services (skip if restart already did it) ──────────────────

if ! $ALREADY_STOPPED; then
    stop_all
    sleep 1
fi

# ── Config check ─────────────────────────────────────────────────────────────

if ! { \
        [ -n "$IDEER_CONFIG_PATH" ] && [ -f "$IDEER_CONFIG_PATH" ] || \
        [ -f backend/config.yaml ] || \
        [ -f config.yaml ]; \
    }; then
    echo "✗ No iDeer config file found."
    echo "  Run 'make setup' (recommended) or 'make config' to generate config.yaml."
    exit 1
fi

"$REPO_ROOT/scripts/config-upgrade.sh"

# ── Install dependencies ────────────────────────────────────────────────────

# Pick a Python for the extras detector. Falls back to plain `python` for
# Windows/Git Bash where only `python` is on PATH.
if command -v python3 >/dev/null 2>&1; then
    DETECT_PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    DETECT_PYTHON="python"
else
    DETECT_PYTHON=""
fi

# Resolve uv extras (postgres, etc.) from UV_EXTRAS or config.yaml so that
# `uv sync` does not wipe out optional dependencies on every restart. See
# scripts/detect_uv_extras.py and Issue #2754 for context. The detector
# whitelists extra names against `^[A-Za-z][A-Za-z0-9_-]*$`, so the unquoted
# splat below only sees valid uv argument tokens.
#
# Stderr is intentionally NOT redirected so the user sees:
#   - whitelist warnings (e.g. "ignoring invalid UV_EXTRAS entry ';'");
#   - detector crashes (e.g. unexpected Python error).
# `|| true` keeps `set -e` from killing dev startup on a detector failure;
# the result is just an empty UV_EXTRAS_FLAGS, which means "no extras".
UV_EXTRAS_FLAGS=""
if [ -n "$DETECT_PYTHON" ]; then
    UV_EXTRAS_FLAGS=$("$DETECT_PYTHON" "$REPO_ROOT/scripts/detect_uv_extras.py" || { echo "[serve.sh] detect_uv_extras.py failed (exit $?) — proceeding without extras" >&2; echo ""; })
fi

if ! $SKIP_INSTALL; then
    echo "Syncing dependencies..."
    if [ -n "$UV_EXTRAS_FLAGS" ]; then
        echo "  • uv extras: $UV_EXTRAS_FLAGS"
    fi
    # `--all-packages` propagates extras into workspace members (ideer-harness
    # in particular). Required for postgres extras — see PR #2584.
    # Intentionally unquoted to splat multiple `--extra X` pairs.
    (cd backend && uv sync --quiet --all-packages $UV_EXTRAS_FLAGS) || { echo "✗ Backend dependency install failed"; exit 1; }
    (cd frontend && pnpm install --silent) || { echo "✗ Frontend dependency install failed"; exit 1; }
    echo "✓ Dependencies synced"
else
    echo "⏩ Skipping dependency install (--skip-install)"
fi

# ── Banner ───────────────────────────────────────────────────────────────────

echo ""
echo "=========================================="
echo "  Starting iDeer"
echo "=========================================="
echo ""
echo "  Mode: $MODE_LABEL"
echo ""
echo "  Services:"
echo "    Gateway     → localhost:8001  (REST API + agent runtime)"
echo "    Worker      → workflow-worker (durable workflow tasks)"
echo "    Frontend    → localhost:3000  (Next.js)"
echo "    Nginx       → localhost:2026  (reverse proxy)"
echo ""

# ── Cleanup handler ──────────────────────────────────────────────────────────

cleanup() {
    local status="${1:-0}"
    trap - INT TERM
    echo ""
    stop_all
    exit "$status"
}

# 仅在非 daemon 模式下设置陷阱，daemon 模式下进程已 detach，不需要陷阱
if ! $DAEMON_MODE; then
    trap 'cleanup 130' INT
    trap 'cleanup 143' TERM
fi

# ── Helper: start a service ──────────────────────────────────────────────────

# run_service NAME COMMAND PORT TIMEOUT
# In daemon mode, wraps with nohup. Waits for port to be ready.
run_service() {
    local name="$1" cmd="$2" port="$3" timeout="$4"

    if _is_port_listening "$port"; then
        echo "  Port $port is in use, attempting to stop existing service..."
        _kill_repo_port "$port"
        sleep 1
        if _is_port_listening "$port"; then
            echo "✗ $name cannot start because port $port is still in use."
            echo "  If it belongs to this worktree, run 'make stop'; otherwise free the port manually."
            cleanup 1
        fi
    fi

    echo "Starting $name..."
    if $DAEMON_MODE; then
        nohup sh -c "$cmd" > /dev/null 2>&1 &
    else
        sh -c "$cmd" &
    fi

    "$REPO_ROOT/scripts/wait-for-port.sh" "$port" "$timeout" "$name" || {
        local logfile="logs/$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').log"
        echo "✗ $name failed to start."
        [ -f "$logfile" ] && tail -20 "$logfile"
        cleanup 1
    }
    echo "✓ $name started on localhost:$port"
}

run_workflow_worker() {
    local worker_pid

    if [ -f "$WORKFLOW_WORKER_PID_FILE" ]; then
        worker_pid=$(cat "$WORKFLOW_WORKER_PID_FILE")
        if [ -n "$worker_pid" ] && kill -0 "$worker_pid" 2>/dev/null && _is_repo_pid "$worker_pid"; then
            echo "✗ Workflow worker cannot start because it is already running (pid $worker_pid)."
            cleanup 1
        fi
        rm -f "$WORKFLOW_WORKER_PID_FILE"
    fi

    echo "Starting Workflow worker..."
    if $DAEMON_MODE; then
        nohup sh -c "cd '$REPO_ROOT/backend' && PYTHONPATH=. uv run python -m app.workflow_worker" > logs/workflow-worker.log 2>&1 &
    else
        (cd backend && PYTHONPATH=. uv run python -m app.workflow_worker > ../logs/workflow-worker.log 2>&1) &
    fi
    worker_pid=$!
    echo "$worker_pid" > "$WORKFLOW_WORKER_PID_FILE"
    sleep 1
    if ! kill -0 "$worker_pid" 2>/dev/null; then
        echo "✗ Workflow worker failed to start."
        tail -20 logs/workflow-worker.log 2>/dev/null || true
        cleanup 1
    fi
    echo "✓ Workflow worker started (pid $worker_pid)"
}

# ── Start services ───────────────────────────────────────────────────────────

mkdir -p logs
mkdir -p temp/client_body_temp temp/proxy_temp temp/fastcgi_temp temp/uwsgi_temp temp/scgi_temp

# 0. Database migrations
# Run from backend/ so relative sqlite_dir ".ideer/data" resolves to
# backend/.ideer/data/ideer.db, matching Gateway startup (env.py further
# resolves from config.yaml and ensures the parent dir exists).
echo "Running database migrations..."
(cd "$REPO_ROOT/backend" && uv run alembic -c packages/harness/ideer/persistence/migrations/alembic.ini upgrade head) || { echo "✗ Database migrations failed"; cleanup 1; }
echo "✓ Database migrations completed"

# 1. Gateway API
run_service "Gateway" \
    "cd backend && PYTHONPATH=. uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 $GATEWAY_EXTRA_FLAGS > ../logs/gateway.log 2>&1" \
    8001 30

# 2. Durable workflow task consumer
run_workflow_worker

# 3. Frontend
run_service "Frontend" \
    "cd frontend && $FRONTEND_CMD > ../logs/frontend.log 2>&1" \
    3000 120

# 4. Nginx
run_service "Nginx" \
    "nginx -g 'daemon off;' -c '$REPO_ROOT/docker/nginx/nginx.local.conf' -p '$REPO_ROOT' > logs/nginx.log 2>&1" \
    2026 10

# ── Ready ────────────────────────────────────────────────────────────────────

echo ""
echo "=========================================="
echo "  ✓ iDeer is running!  [$MODE_LABEL]"
echo "=========================================="
echo ""
echo "  🌐 http://localhost:2026"
echo ""
echo "  Routing: Frontend → Nginx → Gateway"
echo "  API:     /api/langgraph/*  →  Gateway agent runtime"
echo "           /api/*              →  Gateway REST API (8001)"
echo ""
echo "  📋 Logs: logs/{gateway,workflow-worker,frontend,nginx}.log"
echo ""

if $DAEMON_MODE; then
    echo "  🛑 Stop: make stop"
    # Detach — trap is no longer needed
    trap - INT TERM
else
    echo "  Press Ctrl+C to stop all services"
    wait
fi
