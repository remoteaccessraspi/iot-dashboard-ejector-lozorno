#!/usr/bin/env bash
set -u

URL="${HMI_URL:-http://localhost:8000}"
CHROMIUM_BIN="${CHROMIUM_BIN:-chromium}"
LOCK_FILE="/tmp/iot-hmi-kiosk.lock"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "kiosk uz bezi"
  exit 0
fi

if command -v xset >/dev/null 2>&1; then
  xset s off 2>/dev/null || true
  xset -dpms 2>/dev/null || true
  xset s noblank 2>/dev/null || true
fi

while true; do
  echo "cakam na dashboard ${URL}"
  until curl -fsS --max-time 3 "$URL" >/dev/null 2>&1; do
    sleep 2
  done

  echo "spustam chromium"
  "$CHROMIUM_BIN" \
    --kiosk \
    --incognito \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --check-for-update-interval=31536000 \
    --password-store=basic \
    --use-mock-keychain \
    --ozone-platform=wayland \
    "$URL" || true

  echo "chromium skoncil, novy start o 3 s"
  sleep 3
done
