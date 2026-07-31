#!/usr/bin/env bash
set -e

URL="http://localhost:8000"

for i in {1..60}; do
  if curl -fsS "$URL" >/dev/null 2>&1; then
    exec chromium \
      --kiosk --incognito \
      --noerrdialogs --disable-infobars \
      --password-store=basic \
      --use-mock-keychain \
      "$URL"
  fi
  sleep 1
done

exec chromium \
  --kiosk --incognito \
  --noerrdialogs --disable-infobars \
  --password-store=basic \
  --use-mock-keychain \
  "$URL"
