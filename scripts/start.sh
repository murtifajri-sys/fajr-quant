#!/usr/bin/env bash
# Start the full Fajr-Quant Docker stack and wait for the backend to be ready.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/start_fajr_quant.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE"
}

cd "$PROJECT_DIR"

log "Starting Fajr-Quant services..."
docker compose up -d --build

log "Waiting for backend API to be ready..."
waited=0
max_wait=300
while ! curl -s "http://localhost:8000/api/v1/tasks/runs" >/dev/null; do
    if [ "$waited" -ge "$max_wait" ]; then
        log "Backend API did not become ready within ${max_wait}s."
        exit 1
    fi
    sleep 5
    waited=$((waited + 5))
done

log "Backend is ready."
log "Access:"
log "  Frontend : http://localhost:3000"
log "  API      : http://localhost:8000/api/v1"
log "  Flower   : http://localhost:5555"
log "Done."
