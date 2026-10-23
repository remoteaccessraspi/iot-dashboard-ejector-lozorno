# iot-dashboard-ejector-lozorno

Ejector monitoring and control for the Lozorno deployment. Raspberry Pi acts as
Modbus RTU master on a single RS485 bus and serves the HMI over HTTP.

## Bus layout

| Slave ID | Device                                      |
|----------|---------------------------------------------|
| 2        | CK-3083ES_8CH PT100 (t1-t8)                 |
| 3        | CK-7082E_8CH current loop 4-20 mA (i1-i8)   |
| 31       | EM2RS-556 stepper (ETS valve)               |
| 100      | INVT GD20-EU inverter (pressure regulation) |

Pressure channels p1-p8 are converted from i1-i8 inside `Ck7082e8chDevice`.
The GD20 regulates with its own internal PID; the feedback comes from the
inverter's AI2 input, not from the Raspberry Pi.

## Services

```bash
sudo ./install_services.sh     # install and enable systemd units
sudo systemctl status iot-master iot-dashboard
./restart_all.sh               # restart master + dashboard
./update.sh                    # git pull, pip install, restart
```

`iot-master` polls the bus and writes to the RAM MariaDB on port 3307.
`iot-dashboard` serves the HMI on port 8000 and reads the same instance.
`iot-db-archive` copies new history to the SD MariaDB on port 3306.
`sudo ./scripts/install_mariadb_hot.sh` installs the RAM instance; it is separate
from `install_services.sh`. `iot-converter` stays disabled — conversion is done
by the master (`features.converter: false` in `config/common.yaml`). If it is
enabled later, the unit waits for `mariadb-hot`, because `converter_db.py` uses
the `database` port.

## Running the master manually

Stop the service first, otherwise the serial port is busy.

```bash
cd /home/pi/iot-dashboard-ejector-lozorno
sudo systemctl stop iot-master
PYTHONPATH=. .venv/bin/python -u iot_core/runners/modbus_master.py
```

`PYTHONPATH` must point at the repository root, not at `iot_core`.

## GD20 diagnostic

Read-only, never writes a Modbus register. Requires a free serial port.

```bash
sudo systemctl stop iot-master
PYTHONPATH=. .venv/bin/python scripts/test_gd20_pid.py
sudo systemctl start iot-master
```

## Credentials

Database user and password live in `config/secrets.yaml`, which is not tracked.
`config/settings.yaml` lists the partial files. Non-secret values live in
`config/common.yaml` and `config/devices/` (host, port, database name, devices).

```bash
cp config/secrets.yaml.example config/secrets.yaml
chmod 600 config/secrets.yaml
```

Environment variables take precedence over both files, which is the simplest way
to inject credentials from a systemd `EnvironmentFile`:
`EJECTOR_DB_HOST`, `EJECTOR_DB_PORT`, `EJECTOR_DB_USER`, `EJECTOR_DB_PASSWORD`,
`EJECTOR_DB_NAME`. Alarm mail reads `smtp` from the same secrets file.
Recipients live in `config/emails.yaml`.

Credentials are read on every connection, so rotating the password does not
require restarting the services.

## Database

Master and HMI use port 3307. `sudo mysql` without a defaults file reaches the
SD instance on port 3306, not the RAM one.

The RAM schema is loaded by `scripts/mariadb-hot-schema.sh` when the tmpfs
datadir is empty. It applies `db/schema_v1.0.0.sql` and then the migrations.
`db/schema_v1.0.0.sql` drops the base tables, so never run it against the SD
archive.

The migrations are idempotent. Apply them to the archive when a column is added.
Archive sync skips columns the SD tables do not have:

```bash
sudo mysql ejector < db/migrate_invt_gd20.sql
sudo mysql ejector < db/migrate_em2rs_556.sql
sudo mysql ejector < db/migrate_alarms.sql
```

`db/ejector-structure.sql` is a structure dump of the RAM database after those
files. It drops every table. Never run it against a live database.

## Opta

`PWM_PID/` holds the Arduino Opta firmware (Modbus RTU server, slave ID 1) from
the parent project. The Opta is **not** part of this deployment and is not in the
poll cycle; the directory is kept as a reference.
