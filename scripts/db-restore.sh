#!/usr/bin/env bash
# Restore a compressed or plain SQL dump into the Docker Compose db service.
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 path/to/fajr_quant_YYYYmmdd_HHMMSS.sql.gz"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DUMP_FILE="$1"
DB_NAME="${DB_NAME:-fajr_quant}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-rootpass}"

if [ ! -f "$DUMP_FILE" ]; then
    echo "Dump file not found: $DUMP_FILE"
    exit 1
fi

cd "$PROJECT_DIR"

echo "Restoring $DUMP_FILE into database $DB_NAME"
if [[ "$DUMP_FILE" == *.gz ]]; then
    gzip -dc "$DUMP_FILE" | docker compose exec -T db sh -c "mariadb -u'$DB_USER' -p'$DB_PASSWORD' '$DB_NAME' || mysql -u'$DB_USER' -p'$DB_PASSWORD' '$DB_NAME'"
else
    docker compose exec -T db sh -c "mariadb -u'$DB_USER' -p'$DB_PASSWORD' '$DB_NAME' || mysql -u'$DB_USER' -p'$DB_PASSWORD' '$DB_NAME'" < "$DUMP_FILE"
fi
echo "Done."
