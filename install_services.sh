#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
UNIT_DIR=/etc/systemd/system

echo "Installing systemd units from $ROOT/systemd ..."

sudo cp "$ROOT/systemd/iot-master.service" "$UNIT_DIR/"
sudo cp "$ROOT/systemd/relay-engine.service" "$UNIT_DIR/"
sudo cp "$ROOT/systemd/iot-converter.service" "$UNIT_DIR/"
sudo cp "$ROOT/systemd/iot-dashboard.service" "$UNIT_DIR/"

sudo systemctl daemon-reload
sudo systemctl enable --now relay-engine iot-dashboard iot-master
sudo systemctl disable --now iot-converter || true

echo
echo "Status:"
systemctl --no-pager --full status relay-engine iot-dashboard iot-master iot-converter || true
