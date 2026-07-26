#!/usr/bin/env bash
# Create a compressed MariaDB dump from the Docker Compose db service.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
DB_NAME="${DB_NAME:-fajr_quant}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-rootpass}"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
OUT_FILE="$BACKUP_DIR/fajr_quant_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"
cd "$PROJECT_DIR"

if ! docker compose ps db >/dev/null 2>&1; then
    echo "Docker Compose db service is not available."
    exit 1
fi

echo "Writing database dump to $OUT_FILE"
docker compose exec -T db sh -c "mariadb-dump -u'$DB_USER' -p'$DB_PASSWORD' --single-transaction --routines --triggers '$DB_NAME' || mysqldump -u'$DB_USER' -p'$DB_PASSWORD' --single-transaction --routines --triggers '$DB_NAME'" | gzip -c > "$OUT_FILE"
echo "Done."
