#!/bin/bash
# Nainštaluje prázdnu MariaDB v RAM na porte 3307.
# Bežiacu inštanciu na porte 3306 nemení.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FSTAB_LINE="tmpfs /mnt/mysql-hot tmpfs defaults,noatime,size=512M,mode=0755 0 0"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Spusti: sudo $ROOT/scripts/install_mariadb_hot.sh" >&2
  exit 1
fi

install -m 644 "$ROOT/config/mariadb-hot.cnf" /etc/mysql/mariadb-hot.cnf
install -m 644 "$ROOT/systemd/mariadb-hot.service" /etc/systemd/system/mariadb-hot.service
chmod 755 "$ROOT/scripts/mariadb-hot-prepare.sh" "$ROOT/scripts/mariadb-hot-schema.sh"

install -d -m 755 /mnt/mysql-hot
if ! grep -qE '^[^#]*[[:space:]]/mnt/mysql-hot[[:space:]]' /etc/fstab; then
  printf '\n# RAM datadir pre mariadb-hot (port 3307)\n%s\n' "$FSTAB_LINE" >> /etc/fstab
fi

systemctl daemon-reload
mountpoint -q /mnt/mysql-hot || mount /mnt/mysql-hot
systemctl enable --now mariadb-hot.service

echo
echo "Hot inštancia:"
mariadb --defaults-file=/etc/mysql/mariadb-hot.cnf -e "SELECT @@hostname AS host, @@port AS port, @@datadir AS datadir, @@version AS version; SHOW TABLES FROM ejector;"
echo
echo "Porty:"
ss -ltn | awk 'NR==1 || /:3306|:3307/'
