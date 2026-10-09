#!/bin/bash
# Prepne master a HMI na RAM. Karta ostáva archív na porte 3306.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETTINGS="$ROOT/config/settings.yaml"
PATCHED=0
UNITS_REPLACED=0
BACKUP="$(mktemp -d)"

restore_writers() {
  if [[ "$PATCHED" == 1 ]]; then
    return
  fi
  echo "Backfill neprebehol, master a HMI sa vracajú na kartu." >&2
  if [[ "$UNITS_REPLACED" == 1 ]]; then
    cp "$BACKUP/iot-master.service" /etc/systemd/system/
    cp "$BACKUP/iot-dashboard.service" /etc/systemd/system/
    cp "$BACKUP/iot-db-archive.service" /etc/systemd/system/
    systemctl disable iot-db-warm.service 2>/dev/null || true
    rm -f /etc/systemd/system/iot-db-warm.service
    systemctl daemon-reload || true
  fi
  systemctl start iot-master.service iot-dashboard.service iot-db-archive.service || true
}

trap restore_writers EXIT

echo "Zastavujem zápis (master, HMI, sync)..."
systemctl stop iot-master.service iot-dashboard.service iot-db-archive.service
systemctl stop iot-converter.service 2>/dev/null || true

cp /etc/systemd/system/iot-master.service "$BACKUP/"
cp /etc/systemd/system/iot-dashboard.service "$BACKUP/"
cp /etc/systemd/system/iot-db-archive.service "$BACKUP/"
install -m 644 \
  "$ROOT/systemd/iot-master.service" \
  "$ROOT/systemd/iot-dashboard.service" \
  "$ROOT/systemd/iot-db-archive.service" \
  "$ROOT/systemd/iot-db-warm.service" \
  /etc/systemd/system/
UNITS_REPLACED=1
systemctl daemon-reload
systemctl enable iot-db-warm.service iot-db-archive.service

echo "Dopĺňam stĺpec status_code v RAM schéme..."
mariadb --defaults-file=/etc/mysql/mariadb-hot.cnf ejector << 'SQL'
ALTER TABLE invt_gd20
    ADD COLUMN IF NOT EXISTS status_code INT DEFAULT NULL
        COMMENT 'Raw Goodrive status word 0x2100: 1 forward run, 2 reverse run, 3 stop, 4 fault, 5 POFF, 6 pre-exciting'
        AFTER running;
ALTER TABLE invt_gd20_state
    ADD COLUMN IF NOT EXISTS status_code INT DEFAULT NULL
        COMMENT 'Raw Goodrive status word 0x2100: 1 forward run, 2 reverse run, 3 stop, 4 fault, 5 POFF, 6 pre-exciting'
        AFTER running;
SQL

echo "Nahrávam posledných 24 h a stav do RAM..."
systemctl reset-failed iot-db-warm.service || true
systemctl start iot-db-warm.service

python3 - "$SETTINGS" << 'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
original = text

old_db = """database:
  host: 127.0.0.1
  port: 3306
  name: ejector

# RAM inštancia. Služby na ňu zatiaľ nejdú, sync z nej číta.
"""
new_db = """database:
  host: 127.0.0.1
  port: 3307
  name: ejector

# RAM inštancia. Master a HMI sa pripájajú sem.
"""
if old_db in text:
    text = text.replace(old_db, new_db, 1)
elif "database:\n  host: 127.0.0.1\n  port: 3307\n  name: ejector\n" not in text:
    raise SystemExit("settings.yaml nemá očakávaný blok database")

old_sync = """  # RAM je zatiaľ prázdna a master píše na kartu. REPLACE stavu by ten stav zmazal.
  sync_state: false
"""
new_sync = """  # Master píše do RAM. Stav sa dávkou vracia na kartu.
  sync_state: true
"""
if old_sync in text:
    text = text.replace(old_sync, new_sync, 1)

text = text.replace("  purge_archive: false\n", "  purge_archive: true\n", 1)

if "sync_state: true" not in text or "purge_archive: true" not in text:
    raise SystemExit("archive_sync sa nepodarilo prepnúť")
if text != original:
    path.write_text(text, encoding="utf-8")
print("settings: služby idú na port 3307")
PY
PATCHED=1

echo "Spúšťam master a HMI na RAM..."
systemctl start iot-master.service iot-dashboard.service

card_before="$(mariadb -N -e "SELECT COALESCE(MAX(id), 0) FROM ejector.temperature")"
hot_id=""
for _ in $(seq 1 20); do
  hot_id="$(mariadb --defaults-file=/etc/mysql/mariadb-hot.cnf -N -e "SELECT COALESCE(MAX(id), 0) FROM ejector.temperature")"
  if [[ "$hot_id" -gt "$card_before" ]]; then
    break
  fi
  sleep 1
done

if [[ "$hot_id" -le "$card_before" ]]; then
  systemctl start iot-db-archive.service || true
  echo "RAM nedostala novú vzorku (hot=$hot_id, karta=$card_before)." >&2
  exit 1
fi

echo "Nová vzorka je v RAM (id $hot_id). Dávka na kartu..."
systemctl restart iot-db-archive.service
sleep 2

card_after="$(mariadb -N -e "SELECT COALESCE(MAX(id), 0) FROM ejector.temperature")"
if [[ "$card_after" -le "$card_before" ]]; then
  echo "Dávka sa na kartu neuložila (karta=$card_after)." >&2
  exit 1
fi

live_count="$(curl -sf "http://127.0.0.1:8000/api/live?minutes=10" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['time']))")"
echo "HMI live body: $live_count"
echo "Karta dobehla na id $card_after (predtým $card_before)."

trap - EXIT
echo
systemctl --no-pager --full is-active iot-master.service iot-dashboard.service iot-db-archive.service mariadb-hot.service mariadb.service
