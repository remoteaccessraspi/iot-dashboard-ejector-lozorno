#!/bin/bash
set -euo pipefail

echo "Restarting IOT system..."

sudo systemctl restart iot-master
sudo systemctl restart iot-dashboard
# iot-converter intentionally not restarted (disabled; conversion in CK-7082E_8CH)

echo "DONE"
systemctl --no-pager --full is-active iot-master iot-dashboard || true
