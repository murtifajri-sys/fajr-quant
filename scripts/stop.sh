#!/usr/bin/env bash
# Stop the Fajr-Quant Docker stack gracefully.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/stop_fajr_quant.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE"
}

cd "$PROJECT_DIR"

log "Stopping Fajr-Quant services..."
docker compose stop

log "Services stopped."
log "Done."
