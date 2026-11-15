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

`Ck7082e8chDevice` converts each current loop into the matching `p` channel.
i4 and i5 are flow: condenser and evaporator, 0–12.5 l/s. i6, i7 and i8 are
pressure: generator 0–1500 kPa (`p_gen_prim`), evaporator 0–220 kPa, condenser
0–400 kPa. i1–i3 are unused. Loop alarms watch i6–i8 only.

The GD20 regulates with its own internal PID; the feedback comes from the
inverter's AI2 input, not from the Raspberry Pi.

## Services

```bash
sudo ./install_services.sh     # install and enable systemd units
sudo systemctl status iot-master iot-dashboard
./restart_all.sh               # restart master + dashboard
./update.sh                    # git pull, pip install, restart
```

`iot-db-warm` loads the last 24 h and device state into RAM before the master
and dashboard start. `iot-master` polls the bus and writes to the RAM MariaDB
on port 3307. `iot-dashboard` serves the HMI on port 8000 and reads the same
instance. `iot-db-archive` copies new history to the SD MariaDB on port 3306.
`iot-kiosk-watchdog` restarts a dead master, a silent dashboard, or a lost
kiosk session. `sudo ./scripts/install_mariadb_hot.sh` installs the RAM
instance; it is separate from `install_services.sh`. Run it first: master,
dashboard and `iot-db-warm` require `mariadb-hot`, so `install_services.sh`
fails on a Pi without it. `install_services.sh` does not install
`systemd/sudoers-iot-ejector`. That file lets `pi` start, stop and read the
logs of these units without a password. Install it with
`sudo visudo -cf systemd/sudoers-iot-ejector && sudo install -m 440 systemd/sudoers-iot-ejector /etc/sudoers.d/iot-ejector`.

`iot-converter` stays disabled. The master always writes `conversion_table`
itself; it does not read `features.converter`. Do not enable the converter
unit: it starts from id 0, hits the unique `current_loop_id` on rows the
master already wrote, and that error is not caught.

## Temperatures

Start and stop limits are in `config/devices/ck_3083es_8ch.yaml`. `hold_s` is
120 s and `stop_hold_s` is 15 s. A hysteresis of 0 would put both edges on the
center value.

| Channel | YAML now | Running drive stops | Automatic recovery |
|---------|----------|---------------------|--------------------|
| `t_gen_in` (t3) | `ready_min` 80 °C, `ready_hyst` 1 | below 79 °C for 15 s | at or above 81 °C |
| `t_cond_in` (t6) | `ready_max` 28 °C, `ready_max_stable` 30 °C, `ready_hyst` 1 | above 29 °C for 15 s; above 31 °C when INVT is stable | below 27 °C |
| `t_evap_in` (t1) | `ready_min` 18 °C, `ready_hyst` 1 | below 17 °C for 15 s | above 19 °C |

The ordinary RUN button uses only `t_gen_in` and `t_cond_in`. Both must hold
for the whole `hold_s`, with a fresh sample. `t_evap_in` does not grey out
that button. From 17 °C through 19 °C the evaporator keeps its last side: that
band does not start a new stop and does not open the recovery window.

For `t_cond_in` in ordinary RUN (not service), the stop edge depends on INVT
stability. Unstable or missing PID samples use `ready_max + ready_hyst`
(above 29 °C). When the drive is online, running, the sample is fresh, and
`|pid_feedback − setpoint| ≤ p7_trim.invt_tolerance_kpa` (50 kPa), the stop
moves to `ready_max_stable + ready_hyst` (above 31 °C). Losing stability
returns to the 29 °C edge. Start recovery stays below 27 °C.

Outside a service run, each of those stops raises a warning and arms a
temperature restart. A service run shows the warning and leaves the drive
running; these limits do not apply to service RUN. Open S4 and a drive fault
do not arm the restart. After the service session ends, the normal stop
applies again.

Temperature recovery runs only after an automatic temperature stop. It still
needs `t_gen_in` and `t_cond_in` inside their start edges for `hold_s`. After
an evaporator stop it also needs `t_evap_in` above 19 °C for that same hold.
A missing or invalid evaporator sample blocks the automatic start. A manual
STOP, open S4, or a drive fault cancels it.

## Expansion valve

0 % means the valve is fully closed; 100 % is fully open. Saying "close the
valve" means 0 %. After STOP, a drive fault, or power loss the valve moves to
`valve.park_percent` (50 %).

`valve.closed_stop_percent` in `config/devices/em2rs_556.yaml` is the automatic
STOP threshold on actual opening. Default is `0`. While the drive is running,
a fresh valid position at or below that value stops the drive. Set the key to
`na` (any case) to disable this stop. The park move to 50 % does not start the
drive again. Restart waits until `t_cond_in` rises above 29 °C and the normal
start window is true again. Manual STOP, open S4, a drive fault, and red
cavitation cancel that recovery. A blocking alarm only holds it: after Ack and
once the cause has cleared, the drive starts on its own when the start window
holds. A service run does not stop for a closed valve.

The operator sheet is `docs/manuals/prevadzka-teploty-tlaky-alarmy.pdf`.
Rebuild it with `.venv/bin/python docs/manuals/prevadzka-teploty-tlaky-alarmy.py`.
That script imports `reportlab` and the DejaVu fonts in
`/usr/share/fonts/truetype/dejavu/`. The services do not import `reportlab`.

## Config notes

Some keys in device YAML are comments for later work. Python does not read
them: `invt_gd20.pid_defaults`, `em2rs_556.valve.pressure_interlock`,
`safety.scaling_confirmed`, `manual.max_steps`, `p7_trim` has no YAML
setpoint (HMI writes `control_state.em2rs_p7_setpoint_kpa`), and the master
never reads `conversion.interval_sec`. Temperature and cavitation sample ages
are in `config/common.yaml` under `alarms` (`ready_max_age_s`,
`ready_max_gap_s`, `cavitation_max_age_s`, `cavitation_arm_lookback_s`).
`ready_max_age_s` is also the age limit for the valve position in the closed
valve stop. `invt_gd20.stability.max_age_s` decides INVT stability, so it also
moves the `t_cond_in` stop edge. The 0.02 Hz frequency tolerance stays in code.

## Cavitation

Limits are in `config/devices/invt_gd20.yaml` under `cavitation`. The signal is
`p_gen_prim_from_frq`, the inverter AI2 input. Loop pressure `p_gen_prim` on
i6 does not raise this alarm. `p_evap_prim` and `p_cond_prim` are measured and
are not used for cavitation.

`min_kpa` is 750, `frequency_limit_hz` is 45, and `confirm_s` is 10 s. A red
Cavitation alarm is raised only when all of this holds:

- The drive is running, online, and not in its own fault. The sample is at
  most 15 s old.
- AI2 has already reached 750 kPa in this run, or in the history of the last
  3 hours.
- AI2 then falls below 750 kPa and the frequency reaches the 45 Hz ceiling.
  The register step is 0.01 Hz, so 44.98 Hz already counts.
- Both last for 10 s.
- `t_gen_in` is at least 80 °C. Hysteresis does not move this edge. A missing
  temperature is treated as an alarm for the operator.

Outside a service run the drive gets STOP. The bar stays until service presses
Ack and the condition has cleared. Ordinary RUN then also waits for the
temperature window. During a service run the red alarm and the mail remain,
and the drive keeps running.

If `t_gen_in` is below 80 °C at that moment, no red alarm is raised. Outside
service the drive stops and restarts itself after both start temperatures hold
for 2 minutes. A service run does not stop.

A ramp below 750 kPa before the frequency reaches the ceiling is not
cavitation. The pressure drop after a stop is not cavitation either.

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
Recipients live in `config/emails.yaml`. `openai.api_key` in the same secrets
file is stored for other local projects. The master and the HMI do not import
the `openai` package; `load_openai_secrets()` only reads the key.
`docs/OPENAI.md` describes the Platform account and does not hold the key.
`images/openai_wireframe.py`, named in that note, is not in this repository.

The `EJECTOR_DB_*` variables apply in full to `database`. `database_hot` and
`database_archive`, used by archive sync, take only `EJECTOR_DB_USER` and
`EJECTOR_DB_PASSWORD` from the environment.

Services read `secrets.yaml` on every connection, but the database account is
not updated by that. `scripts/mariadb-hot-schema.sh` sets the RAM password
only when `mariadb-hot` starts, and it takes the first indented `user` and
`password` in `secrets.yaml`, so `database` must stay the first section.
To change the password:

1. Edit `config/secrets.yaml`.
2. Run `ALTER USER` for that account on the SD instance (`sudo mysql`).
3. Run `sudo systemctl restart mariadb-hot`. Units that require it restart
   with it. The tmpfs stays mounted, so RAM data survives.

`config/common.yaml` and the device files are read once per process. A change
there needs `./restart_all.sh`, which restarts `iot-master`, `iot-dashboard`
and `iot-db-archive`. `config/emails.yaml` is read when a mail is sent.

## Dependencies

Pins for this Pi (Python 3.13) are in `requirements.txt`. `update.sh` installs
`requirements_pi.txt`, which includes that file, so the two lists stay one list.
`reportlab`, `pillow` and `charset-normalizer` are there for the operator PDF.
A fresh venv does not need the `openai` package.

## Database

Master and HMI use port 3307. `sudo mysql` without a defaults file reaches the
SD instance on port 3306, not the RAM one.

The RAM schema is loaded by `scripts/mariadb-hot-schema.sh` when the tmpfs
datadir is empty. It applies `db/schema_v1.0.0.sql` and then the migrations.
`db/schema_v1.0.0.sql` drops the base tables, so never run it against the SD
archive.

The migrations are idempotent. Apply them to the archive when a column is added.
Archive sync skips columns the SD tables do not have, but a missing table
stops the sync. Apply all three before `iot-db-archive` runs on a new SD
database. `db/init.sql` lists the same order:

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
