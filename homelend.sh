#!/bin/bash
# HomeLend Pro - Start/Stop Script
# Usage: ./homelend.sh start | stop | status | restart | docker | docker-stop
#
# Bare-metal mode (start/stop/restart/status) manages the Next.js frontend only.
# The full platform stack (all FastAPI services + gateway) runs via Docker Compose.
# Use the docker / docker-stop subcommands for the full stack.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"
LOG_DIR="$SCRIPT_DIR/.logs"

mkdir -p "$PID_DIR" "$LOG_DIR"

is_frontend_running() {
    if [ -f "$PID_DIR/frontend.pid" ] && kill -0 "$(cat "$PID_DIR/frontend.pid")" 2>/dev/null; then
        return 0
    fi
    lsof -ti :3000 >/dev/null 2>&1
}

do_start() {
    echo "========================================="
    echo "  HomeLend Pro - Starting Frontend"
    echo "========================================="

    # Start Next.js Frontend
    if is_frontend_running; then
        echo "[Frontend] Already running"
    else
        echo "[Frontend] Starting Next.js on port 3000..."
        cd "$SCRIPT_DIR/frontend"
        nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
        echo $! > "$PID_DIR/frontend.pid"
        echo "[Frontend] Started (PID: $!) — logs: .logs/frontend.log"
    fi

    echo ""
    echo "  Frontend: http://localhost:3000"
    echo ""
    echo "  To run the full platform stack (API services + gateway):"
    echo "  ./homelend.sh docker"
    echo "========================================="
}

do_stop() {
    echo "========================================="
    echo "  HomeLend Pro - Stopping Frontend"
    echo "========================================="

    # Stop Next.js Frontend
    if [ -f "$PID_DIR/frontend.pid" ]; then
        FE_PID=$(cat "$PID_DIR/frontend.pid")
        if kill -0 "$FE_PID" 2>/dev/null; then
            echo "[Frontend] Stopping (PID: $FE_PID)..."
            kill "$FE_PID" 2>/dev/null
            sleep 2
            kill -9 "$FE_PID" 2>/dev/null
        fi
        rm -f "$PID_DIR/frontend.pid"
    fi
    # Force kill ANY process listening on port 3000
    NODE_PIDS=$(lsof -ti :3000 2>/dev/null)
    if [ -n "$NODE_PIDS" ]; then
        echo "[Frontend] Killing remaining processes on port 3000..."
        echo "$NODE_PIDS" | xargs kill -9 2>/dev/null
        sleep 1
    fi
    echo "[Frontend] Stopped"

    echo "========================================="
    echo "  Frontend stopped"
    echo "========================================="
}

do_status() {
    echo "========================================="
    echo "  HomeLend Pro - Status"
    echo "========================================="
    if is_frontend_running; then
        echo "[Frontend] RUNNING  (http://localhost:3000)"
    else
        echo "[Frontend] STOPPED"
    fi
    echo ""
    echo "  For full stack status: docker compose ps"
    echo "========================================="
}

do_docker_start() {
    echo "========================================="
    echo "  HomeLend Pro - Docker Stack (Up)"
    echo "========================================="
    if ! command -v docker &>/dev/null; then
        echo "[Error] docker is not installed or not in PATH."
        exit 1
    fi
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        echo "[Warning] .env not found. Copy .env.example to .env and fill in values."
        echo "          Continuing with defaults (most services will fail without real values)."
    fi
    cd "$SCRIPT_DIR"
    docker compose up -d
    echo ""
    echo "  Gateway:              http://localhost:80"
    echo "  Frontend:             http://localhost:3000"
    echo "  Auth Service:         http://localhost:8001"
    echo "  Property/Listing:     http://localhost:8002"
    echo "  Underwriting Service: http://localhost:8003"
    echo "  Closing Service:      http://localhost:8004"
    echo "  Client CRM Service:   http://localhost:8005"
    echo ""
    echo "  Logs:   docker compose logs -f"
    echo "  Status: docker compose ps"
    echo "========================================="
}

do_docker_stop() {
    echo "========================================="
    echo "  HomeLend Pro - Docker Stack (Down)"
    echo "========================================="
    cd "$SCRIPT_DIR"
    docker compose down
    echo "========================================="
}

case "${1:-}" in
    start)
        do_start
        ;;
    stop)
        do_stop
        ;;
    restart)
        do_stop
        echo ""
        sleep 2
        do_start
        ;;
    status)
        do_status
        ;;
    docker)
        do_docker_start
        ;;
    docker-stop)
        do_docker_stop
        ;;
    *)
        echo "Usage: ./homelend.sh {start|stop|restart|status|docker|docker-stop}"
        echo ""
        echo "  Bare-metal (Next.js frontend only):"
        echo "  start        - Start Frontend (port 3000)"
        echo "  stop         - Stop Frontend"
        echo "  restart      - Stop then start Frontend"
        echo "  status       - Show Frontend running status"
        echo ""
        echo "  Docker Compose (full platform stack with all API services + gateway):"
        echo "  docker       - Start all services with docker compose up -d"
        echo "  docker-stop  - Stop all services with docker compose down"
        exit 1
        ;;
esac
