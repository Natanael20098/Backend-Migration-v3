#!/bin/bash
# HomeLend Pro - Start/Stop Script
# Usage: ./homelend.sh start | stop | status | restart | docker | docker-stop

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"
LOG_DIR="$SCRIPT_DIR/.logs"

mkdir -p "$PID_DIR" "$LOG_DIR"

is_api_running() {
    if [ -f "$PID_DIR/api.pid" ] && kill -0 "$(cat "$PID_DIR/api.pid")" 2>/dev/null; then
        return 0
    fi
    lsof -ti :8080 >/dev/null 2>&1
}

is_frontend_running() {
    if [ -f "$PID_DIR/frontend.pid" ] && kill -0 "$(cat "$PID_DIR/frontend.pid")" 2>/dev/null; then
        return 0
    fi
    lsof -ti :3000 >/dev/null 2>&1
}

do_start() {
    echo "========================================="
    echo "  HomeLend Pro - Starting Services"
    echo "========================================="

    # Start Spring Boot API
    if is_api_running; then
        echo "[API] Already running"
    else
        echo "[API] Starting Spring Boot on port 8080..."
        cd "$SCRIPT_DIR"
        nohup mvn spring-boot:run > "$LOG_DIR/api.log" 2>&1 &
        echo $! > "$PID_DIR/api.pid"
        echo "[API] Started (PID: $!) — logs: .logs/api.log"
    fi

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
    echo "  API:      http://localhost:8080/api"
    echo "  Frontend: http://localhost:3000"
    echo "========================================="
}

do_stop() {
    echo "========================================="
    echo "  HomeLend Pro - Stopping Services"
    echo "========================================="

    # Stop Spring Boot API
    if [ -f "$PID_DIR/api.pid" ]; then
        API_PID=$(cat "$PID_DIR/api.pid")
        if kill -0 "$API_PID" 2>/dev/null; then
            echo "[API] Stopping (PID: $API_PID)..."
            kill "$API_PID" 2>/dev/null
            for i in $(seq 1 10); do
                kill -0 "$API_PID" 2>/dev/null || break
                sleep 1
            done
            kill -9 "$API_PID" 2>/dev/null
        fi
        rm -f "$PID_DIR/api.pid"
    fi
    # Force kill ANY process listening on port 8080
    JAVA_PIDS=$(lsof -ti :8080 2>/dev/null)
    if [ -n "$JAVA_PIDS" ]; then
        echo "[API] Killing remaining processes on port 8080..."
        echo "$JAVA_PIDS" | xargs kill -9 2>/dev/null
        sleep 1
    fi
    echo "[API] Stopped"

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
    echo "  All services stopped"
    echo "========================================="
}

do_status() {
    echo "========================================="
    echo "  HomeLend Pro - Status"
    echo "========================================="
    if is_api_running; then
        echo "[API]      RUNNING  (http://localhost:8080/api)"
    else
        echo "[API]      STOPPED"
    fi
    if is_frontend_running; then
        echo "[Frontend] RUNNING  (http://localhost:3000)"
    else
        echo "[Frontend] STOPPED"
    fi
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
    echo "  Gateway:      http://localhost:80"
    echo "  Frontend:     http://localhost:3000"
    echo "  Java API:     http://localhost:8080/api"
    echo "  Auth Service: http://localhost:8001"
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
        echo "  Bare-metal (Maven + Node, no Docker):"
        echo "  start        - Start API (port 8080) and Frontend (port 3000)"
        echo "  stop         - Stop both services"
        echo "  restart      - Stop then start both services"
        echo "  status       - Show running status"
        echo ""
        echo "  Docker Compose (full stack with gateway):"
        echo "  docker       - Start all services with docker compose up -d"
        echo "  docker-stop  - Stop all services with docker compose down"
        exit 1
        ;;
esac
