#!/usr/bin/env bash
# Monitor data_load task until completion, then restart workers and trigger recommendations.
set -e

TASK_ID="1f0df141-98f0-452f-b150-af8bba73f9be"
LOG_FILE="/home/fajrirog/Fajr-Quant/monitor_and_recommend.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') Monitoring data_load task $TASK_ID..." >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') After completion: restart workers, then trigger recommendations (top 10)." >> "$LOG_FILE"

while true; do
  resp=$(curl -s http://localhost:8000/api/v1/tasks/$TASK_ID || true)
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

echo "$(date '+%Y-%m-%d %H:%M:%S') Restarting workers to pick up new recommendation filter code..." >> "$LOG_FILE"
cd /home/fajrirog/Fajr-Quant
docker compose restart worker >> "$LOG_FILE" 2>&1
sleep 15

echo "$(date '+%Y-%m-%d %H:%M:%S') Triggering recommendations batch (top 10 by score)..." >> "$LOG_FILE"
rec_resp=$(curl -s -X POST http://localhost:8000/api/v1/tasks/recommendations-batch)
echo "$(date '+%Y-%m-%d %H:%M:%S') Recommendations response: $rec_resp" >> "$LOG_FILE"

echo "$(date '+%Y-%m-%d %H:%M:%S') Done. Check status with: curl http://localhost:8000/api/v1/tasks/runs" >> "$LOG_FILE"
