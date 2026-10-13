#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "Updating repository..."
git pull

echo "Activating venv..."
# shellcheck disable=SC1091
source .venv/bin/activate

REQ=requirements_pi.txt
if [[ ! -f "$REQ" ]]; then
  REQ=requirements.txt
fi

echo "Installing dependencies ($REQ)..."
pip install -r "$REQ"

echo "Restarting services..."
sudo systemctl restart iot-master
sudo systemctl restart iot-dashboard
# iot-converter is intentionally disabled (conversion in CK-7082E_8CH)

echo "Update complete."
systemctl --no-pager --full status iot-master iot-dashboard || true
