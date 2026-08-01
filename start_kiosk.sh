#!/usr/bin/env bash
set -euo pipefail

URL="${HMI_URL:-http://localhost:8000}"
CHROMIUM_BIN="${CHROMIUM_BIN:-chromium}"

# počkaj na dashboard (max ~60 s)
for _ in $(seq 1 60); do
  if curl -fsS "$URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# vypni blanking, ak je dostupný (X11 / niektoré session)
if command -v xset >/dev/null 2>&1; then
  xset s off 2>/dev/null || true
  xset -dpms 2>/dev/null || true
  xset s noblank 2>/dev/null || true
fi

exec "$CHROMIUM_BIN" \
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
  "$URL"
