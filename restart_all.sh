#!/bin/bash
set -euo pipefail

echo "Restarting IOT system..."

sudo systemctl restart iot-master
sudo systemctl restart relay-engine
sudo systemctl restart iot-dashboard
# iot-converter intentionally not restarted (disabled; conversion in CurrentLoopDevice)

echo "DONE"
systemctl --no-pager --full is-active iot-master relay-engine iot-dashboard || true
