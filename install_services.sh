#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
UNIT_DIR=/etc/systemd/system

echo "Installing systemd units from $ROOT/systemd ..."

sudo cp "$ROOT/systemd/iot-master.service" "$UNIT_DIR/"
sudo cp "$ROOT/systemd/iot-converter.service" "$UNIT_DIR/"
sudo cp "$ROOT/systemd/iot-dashboard.service" "$UNIT_DIR/"
sudo cp "$ROOT/systemd/iot-kiosk-watchdog.service" "$UNIT_DIR/"
sudo cp "$ROOT/systemd/iot-db-archive.service" "$UNIT_DIR/"
sudo cp "$ROOT/systemd/iot-db-warm.service" "$UNIT_DIR/"

sudo systemctl daemon-reload
sudo systemctl enable iot-db-warm iot-db-archive
sudo systemctl disable --now relay-engine || true
sudo systemctl enable --now iot-dashboard iot-master iot-kiosk-watchdog
sudo systemctl disable --now iot-converter || true

echo
echo "Status:"
systemctl --no-pager --full status iot-dashboard iot-master iot-kiosk-watchdog iot-converter || true
