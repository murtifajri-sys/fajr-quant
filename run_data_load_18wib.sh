#!/usr/bin/env bash
# One-time data_load full run at 18:00 WIB to verify race-condition fix.
set -e

LOG_FILE="/home/fajrirog/Fajr-Quant/run_data_load_18wib.log"
TARGET_HOUR=18
TARGET_MINUTE=0

now_epoch=$(date +%s)
today=$(date +%Y-%m-%d)
target_epoch=$(date -d "$today $TARGET_HOUR:$TARGET_MINUTE:00" +%s)

if [ "$now_epoch" -ge "$target_epoch" ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') Target time already passed today, running now." >> "$LOG_FILE"
else
  sleep_seconds=$((target_epoch - now_epoch))
  echo "$(date '+%Y-%m-%d %H:%M:%S') Sleeping until $today $TARGET_HOUR:$TARGET_MINUTE:00 WIB ($sleep_seconds seconds)..." >> "$LOG_FILE"
  sleep "$sleep_seconds"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Triggering full data_load..." >> "$LOG_FILE"
cd /home/fajrirog/Fajr-Quant
rec_resp=$(curl -s -X POST http://localhost:8000/api/v1/tasks/data-load)
echo "$(date '+%Y-%m-%d %H:%M:%S') Response: $rec_resp" >> "$LOG_FILE"

task_id=$(echo "$rec_resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id',''))" 2>/dev/null || true)
if [ -z "$task_id" ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') Failed to get task_id." >> "$LOG_FILE"
  exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Monitoring task $task_id..." >> "$LOG_FILE"
while true; do
  resp=$(curl -s http://localhost:8000/api/v1/tasks/$task_id || true)
  if [ -z "$resp" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') API unavailable, retrying..." >> "$LOG_FILE"
    sleep 120
    continue
  fi
  status=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
  progress=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('progress',0)}% ({d.get('processed_tickers',0)}/{d.get('total_tickers',0)}) ok={d.get('succeeded_tickers',0)} fail={d.get('failed_tickers',0)}\")" 2>/dev/null || echo "?")
  echo "$(date '+%Y-%m-%d %H:%M:%S') data_load status=$status progress=$progress" >> "$LOG_FILE"

  if [ "$status" = "SUCCESS" ] || [ "$status" = "FAILURE" ] || [ "$status" = "CANCELLED" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') data_load finished with status=$status" >> "$LOG_FILE"
    break
  fi
  sleep 120
done

echo "$(date '+%Y-%m-%d %H:%M:%S') Done. Check status with: curl http://localhost:8000/api/v1/tasks/runs" >> "$LOG_FILE"
