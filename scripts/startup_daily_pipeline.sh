#!/usr/bin/env bash
# Auto-run daily pipeline on boot if it was missed (e.g. PC was off at 18:00 WIB).
# Only triggers after 18:00 WIB and if no daily_pipeline task exists for today.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/startup_daily_pipeline.log"
API_URL="http://localhost:8000/api/v1"
MAX_WAIT=300  # seconds

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"
}

log "=== startup_daily_pipeline.sh started ==="

# Wait for the backend API to be available.
waited=0
while ! curl -s "$API_URL/tasks/runs" >/dev/null; do
    if [ "$waited" -ge "$MAX_WAIT" ]; then
        log "API not ready after ${MAX_WAIT}s, aborting."
        exit 1
    fi
    log "API not ready, waiting..."
    sleep 10
    waited=$((waited + 10))
done
log "API ready."

# Only run after market close (18:00 WIB).
hour_wib=$(TZ=Asia/Jakarta date +%H)
if [ "$hour_wib" -lt 18 ]; then
    log "Current WIB time is ${hour_wib}:00 (before 18:00). Skip."
    exit 0
fi

# Check if daily_pipeline already ran today (WIB date), in any status.
today_wib=$(TZ=Asia/Jakarta date +%Y-%m-%d)
log "Checking daily_pipeline status for $today_wib..."

runs=$(curl -s "$API_URL/tasks/runs?limit=100")

# Check using jq if available; otherwise fall back to a Python temp-file helper.
if command -v jq >/dev/null 2>&1; then
    match=$(echo "$runs" | jq -r --arg today "$today_wib" '
        [.[] | select(.task_name == "daily_pipeline")]
        | map(.started_at | split("T")[0])
        | if index($today) then "found" else "not_found" end
    ')
else
    tmpfile=$(mktemp)
    echo "$runs" > "$tmpfile"
    match=$(python3 "$tmpfile" "$today_wib" <<'PY'
import sys, json
from datetime import datetime, timedelta
path, today = sys.argv[1], sys.argv[2]
data = json.load(open(path))
for r in data:
    if r.get("task_name") == "daily_pipeline":
        started = r.get("started_at", "")
        utc = datetime.fromisoformat(started.replace("Z", "+00:00")).replace(tzinfo=None)
        wib = utc + timedelta(hours=7)
        if wib.strftime("%Y-%m-%d") == today:
            print("found")
            sys.exit(0)
print("not_found")
PY
)
    rm -f "$tmpfile"
fi

if [ "$match" = "found" ]; then
    log "daily_pipeline already has a run today ($today_wib). Skip."
    exit 0
fi

log "No daily_pipeline run today. Triggering now..."
resp=$(curl -s -X POST "$API_URL/tasks/daily-pipeline")
task_id=$(echo "$resp" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))" 2>/dev/null || true)
log "Triggered. Response: $resp"
if [ -n "$task_id" ]; then
    log "Task ID: $task_id"
fi
log "Done."
