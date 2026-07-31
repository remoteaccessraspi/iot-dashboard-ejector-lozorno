#!/bin/bash
set -e

PORT="/dev/ttyACM0"
FQBN="arduino:mbed_opta:opta"
PROJECT="/home/pi/apps/iot_dashboard/PWM_PID"
BAUD="115200"

echo "=============================="
echo "Opta build + upload + monitor"
echo "=============================="

echo "Kontrola portu $PORT"

if lsof "$PORT" >/dev/null 2>&1; then
    echo "Port je obsadený, zatváram monitor..."
    fuser -k "$PORT" || true
    sleep 2
fi

echo
echo "1) Compile"
arduino-cli compile --fqbn "$FQBN" "$PROJECT"

echo
echo "2) Upload"
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$PROJECT"

echo
echo "3) Čakanie na návrat portu"

for i in {1..10}; do
    if [ -e "$PORT" ]; then
        break
    fi
    sleep 1
done

echo
echo "4) Serial monitor"
echo "CTRL+C ukončí monitor"
echo

exec arduino-cli monitor -p "$PORT" -c baudrate="$BAUD"
