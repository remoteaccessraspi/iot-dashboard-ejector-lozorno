# iot-dashboard-ejector-lozorno

Ejector monitoring and control for the Lozorno deployment. Raspberry Pi acts as
Modbus RTU master on a single RS485 bus and serves the HMI over HTTP.

## Bus layout

| Slave ID | Device                                      |
|----------|---------------------------------------------|
| 2        | PT100 temperature module (t1-t8)            |
| 3        | Current loop module 4-20 mA (i1-i8)         |
| 100      | INVT GD20-EU inverter (pressure regulation) |

Pressure channels p1-p8 are converted from i1-i8 inside `CurrentLoopDevice`.
The GD20 regulates with its own internal PID; the feedback comes from the
inverter's AI2 input, not from the Raspberry Pi.

## Services

```bash
sudo ./install_services.sh     # install and enable systemd units
sudo systemctl status iot-master iot-dashboard
./restart_all.sh               # restart master + dashboard
./update.sh                    # git pull, pip install, restart
```

`iot-master` polls the bus and writes to MariaDB, `iot-dashboard` serves the HMI
on port 8000. `iot-converter` stays disabled — conversion is done by the master
(`features.converter: false` in `config/settings.yaml`).

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
`config/settings.yaml` holds only non-secret values (host, port, database name).

```bash
cp config/secrets.yaml.example config/secrets.yaml
chmod 600 config/secrets.yaml
```

Environment variables take precedence over both files, which is the simplest way
to inject credentials from a systemd `EnvironmentFile`:
`EJECTOR_DB_HOST`, `EJECTOR_DB_PORT`, `EJECTOR_DB_USER`, `EJECTOR_DB_PASSWORD`,
`EJECTOR_DB_NAME`.

Credentials are read on every connection, so rotating the password does not
require restarting the services.

## Database

```bash
sudo mysql -e "CREATE DATABASE IF NOT EXISTS ejector CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql ejector < db/schema_v1.0.0.sql
sudo mysql ejector < db/migrate_invt_gd20.sql
```

`db/ejector-structure.sql` is a dump of the resulting structure and is kept for
reference only — it drops every table, so never run it against a live database.

## Opta

`PWM_PID/` holds the Arduino Opta firmware (Modbus RTU server, slave ID 1) from
the parent project. The Opta is **not** part of this deployment and is not in the
poll cycle; the directory is kept as a reference.
