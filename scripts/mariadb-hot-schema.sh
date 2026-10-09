#!/bin/bash
# Nahrá prázdnu schému ejector, keď je datadir čerstvý (typicky po reboote).
set -euo pipefail

CNF=/etc/mysql/mariadb-hot.cnf
ROOT=/home/pi/iot-dashboard-ejector-lozorno
MARKER=/mnt/mysql-hot/data/.schema_loaded

ready=0
for _ in $(seq 1 100); do
  if mariadb --defaults-file="$CNF" -e "SELECT 1" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.2
done
if [[ "$ready" -ne 1 ]]; then
  echo "mariadb-hot neprijíma spojenie" >&2
  exit 1
fi

if [[ ! -f "$MARKER" ]]; then
  mariadb --defaults-file="$CNF" -e \
    "CREATE DATABASE IF NOT EXISTS ejector CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  mariadb --defaults-file="$CNF" ejector < "$ROOT/db/schema_v1.0.0.sql"
  mariadb --defaults-file="$CNF" ejector < "$ROOT/db/migrate_invt_gd20.sql"
  mariadb --defaults-file="$CNF" ejector < "$ROOT/db/migrate_em2rs_556.sql"

  touch "$MARKER"
  chown mysql:mysql "$MARKER"
  chmod 640 "$MARKER"
fi

# Po reboote install-db zmaže účty. Rovnaký používateľ ako na karte, heslo zo secrets.
python3 - "$ROOT/config/secrets.yaml" << 'PY' | mariadb --defaults-file="$CNF"
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")

def field(name):
    match = re.search(rf"(?m)^  {name}:\s*(.+?)\s*$", text)
    if not match:
        raise SystemExit(f"secrets.yaml nemá database.{name}")
    value = match.group(1).strip().strip("'\"")
    return value.replace("\\", "\\\\").replace("'", "''")

user = field("user")
password = field("password")
for host in ("127.0.0.1", "localhost"):
    print(f"CREATE USER IF NOT EXISTS '{user}'@'{host}' IDENTIFIED BY '{password}';")
    print(f"ALTER USER '{user}'@'{host}' IDENTIFIED BY '{password}';")
    print(f"GRANT ALL PRIVILEGES ON ejector.* TO '{user}'@'{host}';")
print("FLUSH PRIVILEGES;")
PY
