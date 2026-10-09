#!/bin/bash
# Zapne dávkový sync RAM -> SD. Master aj HMI ostávajú na porte 3306.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Spusti: sudo $ROOT/scripts/install_archive_sync.sh" >&2
  exit 1
fi

install -m 644 "$ROOT/systemd/iot-db-archive.service" /etc/systemd/system/iot-db-archive.service
chmod 755 "$ROOT/scripts/mariadb-hot-schema.sh"

# Účet dbapp na RAM inštancii (schema skript beží pri štarte).
systemctl restart mariadb-hot.service
systemctl is-active --quiet mariadb-hot.service

systemctl daemon-reload
systemctl stop iot-db-archive.service 2>/dev/null || true

echo "Prvá dávka (len watermark, bez kopírovania starej histórie):"
sudo -u pi env PYTHONPATH="$ROOT" \
  "$ROOT/.venv/bin/python" -u "$ROOT/iot_core/runners/archive_sync.py" --once

echo "Skúška cez pomocnú tabuľku:"
sudo -u pi env PYTHONPATH="$ROOT" \
  "$ROOT/.venv/bin/python" -u "$ROOT/iot_core/runners/archive_sync.py" --probe

systemctl enable --now iot-db-archive.service

echo
systemctl --no-pager --full status iot-db-archive.service mariadb-hot.service
