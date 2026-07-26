#!/usr/bin/env bash
# Install the Fajr-Quant systemd service so the stack starts on boot
# and stops gracefully on shutdown.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/fajr-quant.service"
SYSTEMD_PATH="/etc/systemd/system/fajr-quant.service"

if [ "$EUID" -ne 0 ]; then
    echo "Installing systemd service requires root. Re-running with sudo..."
    exec sudo "$0" "$@"
fi

cp "$SERVICE_FILE" "$SYSTEMD_PATH"
chmod 644 "$SYSTEMD_PATH"

systemctl daemon-reload
systemctl enable fajr-quant.service

echo "Systemd service installed at $SYSTEMD_PATH"
echo "Start now with: sudo systemctl start fajr-quant"
echo "Check status with: sudo systemctl status fajr-quant"
