#!/bin/bash
# Pripraví tmpfs a systémové tabuľky pre RAM inštanciu.
# Po reboote je /mnt/mysql-hot prázdny, takže install-db beží znova.
set -euo pipefail

MOUNT=/mnt/mysql-hot
DATA="$MOUNT/data"

mkdir -p "$MOUNT"
if ! findmnt -n "$MOUNT" >/dev/null 2>&1; then
  mount -t tmpfs -o defaults,noatime,size=512M,mode=0755 tmpfs "$MOUNT"
fi

install -d -o mysql -g mysql -m 750 "$DATA" "$MOUNT/tmp"
install -d -o mysql -g mysql -m 755 /run/mysqld

if [[ ! -d "$DATA/mysql" ]]; then
  mariadb-install-db \
    --defaults-file=/etc/mysql/mariadb-hot.cnf \
    --datadir="$DATA" \
    --user=mysql \
    --auth-root-authentication-method=socket
fi
