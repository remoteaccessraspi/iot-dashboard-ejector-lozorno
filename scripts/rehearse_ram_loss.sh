#!/bin/bash
# Simuluje výpadok RAM bez reštartu Pi.
# Zmaže len /mnt/mysql-hot. Karta na porte 3306 ostáva.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOT=(mariadb --defaults-file=/etc/mysql/mariadb-hot.cnf)
FAILED=1

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Spusti: sudo $ROOT/scripts/rehearse_ram_loss.sh" >&2
  exit 1
fi

recover() {
  if [[ "$FAILED" == 0 ]]; then
    return
  fi
  echo "Obnova RAM nevyšla, skúšam služby naštartovať znova." >&2
  systemctl start mariadb-hot.service || true
  systemctl stop iot-db-warm.service || true
  systemctl reset-failed iot-db-warm.service || true
  systemctl start iot-db-warm.service || true
  systemctl start iot-master.service iot-dashboard.service iot-db-archive.service || true
}

trap recover EXIT

echo "Zastavujem zápis..."
systemctl stop iot-master.service iot-dashboard.service iot-db-archive.service
systemctl stop iot-db-warm.service || true

echo "Mažem RAM datadir a spúšťam ho ako po reboote..."
systemctl stop mariadb-hot.service
rm -rf /mnt/mysql-hot/data /mnt/mysql-hot/tmp
systemctl reset-failed mariadb-hot.service iot-db-warm.service || true
systemctl start mariadb-hot.service
systemctl start iot-db-warm.service

rows="$("${HOT[@]}" -N -e "SELECT COUNT(*) FROM ejector.temperature")"
has_status="$("${HOT[@]}" -N -e "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='ejector' AND table_name='invt_gd20' AND column_name='status_code'")"
state_rows="$("${HOT[@]}" -N -e "SELECT COUNT(*) FROM ejector.control_state")"

if [[ "$rows" -lt 100 || "$has_status" != "1" || "$state_rows" -lt 1 ]]; then
  echo "RAM po obnove: temperature=$rows status_code=$has_status control_state=$state_rows" >&2
  exit 1
fi

echo "RAM má znova ${rows} vzoriek teploty a stav zariadení. Spúšťam služby..."
systemctl start iot-master.service iot-dashboard.service

card_before="$(mariadb -N -e "SELECT COALESCE(MAX(id), 0) FROM ejector.temperature")"
hot_id=""
for _ in $(seq 1 20); do
  hot_id="$("${HOT[@]}" -N -e "SELECT COALESCE(MAX(id), 0) FROM ejector.temperature")"
  if [[ "$hot_id" -gt "$card_before" ]]; then
    break
  fi
  sleep 1
done

if [[ "$hot_id" -le "$card_before" ]]; then
  systemctl start iot-db-archive.service || true
  echo "Po obnove neprišla nová vzorka (hot=$hot_id, karta=$card_before)." >&2
  exit 1
fi

systemctl restart iot-db-archive.service
sleep 2
card_after="$(mariadb -N -e "SELECT COALESCE(MAX(id), 0) FROM ejector.temperature")"
live_count="$(curl -sf "http://127.0.0.1:8000/api/live?minutes=10" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['time']))")"

if [[ "$card_after" -le "$card_before" || "$live_count" -lt 1 ]]; then
  echo "Kontrola zlyhala: karta=$card_after hot=$hot_id graf=$live_count" >&2
  exit 1
fi

FAILED=0
trap - EXIT
echo "Obnova RAM prešla. Teplota v RAM: ${rows} riadkov, nová vzorka id ${hot_id}, graf ${live_count} bodov, karta id ${card_after}."
systemctl --no-pager --full is-active iot-master.service iot-dashboard.service iot-db-archive.service mariadb-hot.service
