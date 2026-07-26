#!/usr/bin/env bash
# Start services if needed, then run broker-flow backfill in auto-loop mode.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
LOG_FILE="$PROJECT_DIR/logs/backfill.log"
LIMIT="${1:-200}"
PERIOD_DAYS="${2:-30}"
UNIVERSE="${3:-idx}"
MODE="${4:-partial}"
MAX_BATCHES="${MAX_BATCHES:-0}"
POLL_SECONDS="${POLL_SECONDS:-30}"
TARGET_PARTIAL="${TARGET_PARTIAL:-0}"
TARGET_MISSING="${TARGET_MISSING:-0}"
STALL_BATCHES="${STALL_BATCHES:-2}"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE"
}

log_err() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE" >&2
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        log "Required command not found: $1"
        exit 1
    fi
}

require_cmd docker
require_cmd curl
require_cmd python3

cd "$PROJECT_DIR"

api_get() {
    curl -sS "$1"
}

coverage_json() {
    api_get "http://localhost:8000/api/v1/tasks/broker-flow-backfill/coverage?period_days=${PERIOD_DAYS}&universe=${UNIVERSE}&limit=200"
}

coverage_field() {
    local field="$1"
    printf '%s' "$2" | python3 -c "import json,sys; print(json.load(sys.stdin).get('${field}', ''))"
}

log_coverage() {
    local payload="$1"
    local complete partial missing avg
    complete="$(coverage_field complete_tickers "$payload")"
    partial="$(coverage_field partial_tickers "$payload")"
    missing="$(coverage_field missing_tickers "$payload")"
    avg="$(coverage_field average_coverage_ratio "$payload")"
    log "Coverage complete=${complete:-0} partial=${partial:-0} missing=${missing:-0} avg=${avg:-0}"
}

notify_token_expired() {
    local task_id="$1"
    local detail="$2"
    docker compose exec -T backend python -c "
from app.core.db import SessionLocal
from app.services.notifier.telegram import send_token_expired_alert

db = SessionLocal()
try:
    send_token_expired_alert(
        db,
        task_name='broker_flow_backfill',
        detail='task_id=${task_id} | ${detail}'[:200],
    )
finally:
    db.close()
" >/dev/null 2>&1 || true
}

detect_token_expired() {
    printf '%s' "$1" | rg -q "Stockbit token expired \(401\)|token expired|unauthorized"
}

trigger_all_batch() {
    local resp task_id
    resp="$(curl -sS -X POST "http://localhost:8000/api/v1/tasks/broker-flow-backfill?limit=${LIMIT}&period_days=${PERIOD_DAYS}&universe=${UNIVERSE}")"
    task_id="$(printf '%s' "$resp" | python3 -c "import json,sys; print(json.load(sys.stdin).get('task_id',''))" 2>/dev/null || true)"
    if [ -z "$task_id" ]; then
        log "Failed to read task_id from generic backfill response: $resp"
        exit 1
    fi
    printf '%s' "$task_id"
}

trigger_partial_batch() {
    docker compose exec -T backend python -c "
from app.core.db import SessionLocal
from app.services.data_loader import broker_flow_coverage_summary
from app.workers.tasks import run_broker_flow_backfill

db = SessionLocal()
try:
    summary = broker_flow_coverage_summary(db, period_days=${PERIOD_DAYS}, universe='${UNIVERSE}', limit=200)
    partials = [item['ticker'] for item in summary['items'] if item.get('status') == 'partial']
    if not partials:
        print('TASK_ID:')
    else:
        task = run_broker_flow_backfill.delay(len(partials), ${PERIOD_DAYS}, '${UNIVERSE}', partials, None)
        print(f'TASK_ID:{task.id}')
finally:
    db.close()
" | rg -o 'TASK_ID:[0-9a-fA-F-]{36}' | tail -n 1 | cut -d: -f2-
}

poll_task() {
    local task_id="$1"
    local status processed total failed stage payload
    while true; do
        payload="$(api_get "http://localhost:8000/api/v1/tasks/${task_id}")"
        status="$(printf '%s' "$payload" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || true)"
        processed="$(printf '%s' "$payload" | python3 -c "import json,sys; print(json.load(sys.stdin).get('processed_tickers',0))" 2>/dev/null || true)"
        total="$(printf '%s' "$payload" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total_tickers',0))" 2>/dev/null || true)"
        failed="$(printf '%s' "$payload" | python3 -c "import json,sys; print(json.load(sys.stdin).get('failed_tickers',0))" 2>/dev/null || true)"
        stage="$(printf '%s' "$payload" | python3 -c "import json,sys; print(json.load(sys.stdin).get('stage',''))" 2>/dev/null || true)"
        log_err "Task ${task_id} status=${status:-unknown} processed=${processed:-0}/${total:-0} failed=${failed:-0} stage=${stage:-n/a}"
        if detect_token_expired "$payload"; then
            log_err "Detected token-expired signal on task ${task_id}. Sending Telegram alert."
            notify_token_expired "$task_id" "Stockbit token expired during backfill"
        fi
        case "$status" in
            SUCCESS|FAILURE|CANCELLED|ORPHANED)
                printf '%s' "$status"
                return 0
                ;;
        esac
        sleep "$POLL_SECONDS"
    done
}

log "Starting Fajr-Quant services..."
docker compose up -d

log "Waiting for backend API..."
waited=0
max_wait=300
until curl -sS "http://localhost:8000/api/v1/tasks/runs" >/dev/null; do
    if [ "$waited" -ge "$max_wait" ]; then
        log "Backend API did not become ready within ${max_wait}s."
        exit 1
    fi
    sleep 5
    waited=$((waited + 5))
done

log "Auto-loop broker-flow backfill: mode=$MODE limit=$LIMIT period_days=$PERIOD_DAYS universe=$UNIVERSE max_batches=$MAX_BATCHES poll=${POLL_SECONDS}s"
initial_coverage="$(coverage_json)"
log_coverage "$initial_coverage"
previous_signature="$(printf '%s' "$initial_coverage" | python3 -c "import json,sys; p=json.load(sys.stdin); print(f\"{p.get('complete_tickers',0)}:{p.get('partial_tickers',0)}:{p.get('missing_tickers',0)}:{p.get('average_coverage_ratio',0)}\")")"
stalled_batches=0

batch=1
while true; do
    current_coverage="$(coverage_json)"
    partial_count="$(coverage_field partial_tickers "$current_coverage")"
    missing_count="$(coverage_field missing_tickers "$current_coverage")"

    if [ "${partial_count:-0}" -le "$TARGET_PARTIAL" ] && [ "${missing_count:-0}" -le "$TARGET_MISSING" ]; then
        log "Target reached. Stopping loop."
        break
    fi

    if [ "$MAX_BATCHES" -gt 0 ] && [ "$batch" -gt "$MAX_BATCHES" ]; then
        log "Reached MAX_BATCHES=$MAX_BATCHES. Stopping loop."
        break
    fi

    if [ "$MODE" = "partial" ]; then
        if [ "${partial_count:-0}" -le 0 ]; then
            log "No partial tickers left. Stopping loop."
            break
        fi
        task_id="$(trigger_partial_batch)"
        if [ -z "$task_id" ]; then
            log "No partial task was created. Stopping loop."
            break
        fi
        log "Batch $batch triggered partial-only task_id=$task_id"
    else
        task_id="$(trigger_all_batch)"
        log "Batch $batch triggered generic task_id=$task_id"
    fi

    final_status="$(poll_task "$task_id")"
    log "Batch $batch finished with status=$final_status"
    latest_coverage="$(coverage_json)"
    log_coverage "$latest_coverage"
    current_signature="$(printf '%s' "$latest_coverage" | python3 -c "import json,sys; p=json.load(sys.stdin); print(f\"{p.get('complete_tickers',0)}:{p.get('partial_tickers',0)}:{p.get('missing_tickers',0)}:{p.get('average_coverage_ratio',0)}\")")"
    if [ "$current_signature" = "$previous_signature" ]; then
        stalled_batches=$((stalled_batches + 1))
        log "Coverage unchanged after batch $batch (stall ${stalled_batches}/${STALL_BATCHES})."
        if [ "$stalled_batches" -ge "$STALL_BATCHES" ]; then
            log "Stopping loop because coverage is stalled."
            break
        fi
    else
        stalled_batches=0
        previous_signature="$current_signature"
    fi

    batch=$((batch + 1))
done

log "Done."
