import json
from datetime import timedelta

from pymysql.cursors import DictCursor

from iot_core.core.config import load_config
from iot_core.service_mode import RUN_SOURCE, service_is_fresh
from iot_core.ready import (
    READY_MAX_AGE_S,
    condenser_high,
    generator_cold,
    start_allowed,
    temperature_channel,
)


COMM_LOSS = "COMM_LOSS"
GD20_FAULT = "GD20_FAULT"
EM2RS_FAULT = "EM2RS_FAULT"
CAVITATION = "CAVITATION"
T_GEN_LOW = "T_GEN_LOW"
T_COND_HIGH = "T_COND_HIGH"
TEMP_SOURCE = "ck_3083es"
LOOP_RANGE = "LOOP_RANGE"
LOOP_SOURCE = "ck_7082e"
# 0x3000 má krok 0.01 Hz. Strop 50.00 Hz preto berieme od 49.98 Hz.
_LIMIT_TOLERANCE_HZ = 0.02
# Po reštarte mastera sa „slučka už bola v poriadku“ dohľadá v histórii.
_ARM_LOOKBACK_S = 3 * 3600
_SAMPLE_MAX_AGE_S = 15


def drive_fault(status_code, fault_code):

    if status_code is not None and int(status_code) == 4:
        return True

    if fault_code in (None, 0):
        return False

    try:
        return int(fault_code) != 0
    except (TypeError, ValueError):
        return True


def _details(value):

    if value is None:
        return None

    if isinstance(value, str):
        return value

    return json.dumps(value, ensure_ascii=False)


class AlarmBook:

    def __init__(
        self,
        repo,
        comm_fails=3,
        loop_low=3.5,
        loop_high=21.0,
        channels=(6, 7, 8),
        loop_max_age_s=10,
        cavitation=None,
        temperature=None,
        notifier=None,
        service_idle_s=30 * 60,
    ):

        self.repo = repo
        self.comm_fails = int(comm_fails)
        self.loop_low = float(loop_low)
        self.loop_high = float(loop_high)
        self.channels = tuple(int(channel) for channel in channels)
        self.loop_max_age_s = float(loop_max_age_s)
        spec = cavitation or {}
        self.cavitation_enabled = bool(spec.get("enabled", cavitation is not None))
        self.cavitation_min_kpa = float(spec.get("min_kpa", 750))
        self.cavitation_confirm_s = float(spec.get("confirm_s", 30))
        self.cavitation_limit_hz = float(spec.get("frequency_limit_hz", 50))
        self._cavitation_armed = False
        self._cavitation_below_since = None
        temp = temperature or {}
        self.temp_enabled = bool(temp.get("enabled", temperature is not None))
        self.temp_stop_hold_s = float(temp.get("stop_hold_s", 15))
        self.temp_channels = temp.get("channels") or {}
        self._temp_values = None
        self._cond_high_since = None
        self.service_idle_s = float(service_idle_s)
        self._service_bypass = False
        self.start_check = None
        self.notifier = notifier

    def note_link(self, conn, source, device_id, ok, inhibit, now):

        device_id = int(device_id)
        row = self.repo.get_link(conn, source, device_id)

        if row is None:
            row = {
                "source": source,
                "device_id": device_id,
                "online": 0,
                "fail_streak": 0,
                "last_ok_ts": None,
                "last_fail_ts": None,
            }

        if ok:
            row["online"] = 1
            row["fail_streak"] = 0
            row["last_ok_ts"] = now
            self.repo.save_link(conn, row)
            self._clear(conn, COMM_LOSS, source, device_id, now)
            return

        streak = int(row["fail_streak"]) + 1
        row["online"] = 0
        row["fail_streak"] = streak
        row["last_fail_ts"] = now
        self.repo.save_link(conn, row)

        if streak < self.comm_fails:
            return

        self._raise(
            conn,
            {
                "code": COMM_LOSS,
                "source": source,
                "device_id": device_id,
                "class": "ALARM",
                "message": f"no reply from {source}",
                "details": {"fail_streak": streak},
                "latched": 1,
                "inhibit_run": 1 if inhibit else 0,
                "release_policy": "ACK",
            },
            now,
        )

    def observe(self, conn, now):

        gd20 = self.repo.read_gd20(conn)

        if gd20 and int(gd20.get("online") or 0):
            status = gd20.get("status_code")
            fault = gd20.get("fault_code")
            device_id = int(gd20.get("device_id") or 0)

            if drive_fault(status, fault):
                if fault not in (None, 0):
                    message = f"GD20 fault {int(fault)}"
                else:
                    message = "GD20 status FAULT"
                self._raise(
                    conn,
                    {
                        "code": GD20_FAULT,
                        "source": "invt_gd20",
                        "device_id": device_id,
                        "class": "ALARM",
                        "message": message,
                        "details": {"status_code": status, "fault_code": fault},
                        "latched": 1,
                        "inhibit_run": 1,
                        "release_policy": "ACK",
                    },
                    now,
                )
            else:
                self._clear(conn, GD20_FAULT, "invt_gd20", device_id, now)

        em2rs = self.repo.read_em2rs(conn)

        if em2rs and int(em2rs.get("online") or 0):
            device_id = int(em2rs.get("device_id") or 0)

            if int(em2rs.get("alarm") or 0):
                text = em2rs.get("alarm_text") or "EM2RS alarm"
                self._raise(
                    conn,
                    {
                        "code": EM2RS_FAULT,
                        "source": "em2rs_556",
                        "device_id": device_id,
                        "class": "ALARM",
                        "message": str(text)[:255],
                        "details": None,
                        "latched": 1,
                        "inhibit_run": 0,
                        "release_policy": "ACK",
                    },
                    now,
                )
            else:
                self._clear(conn, EM2RS_FAULT, "em2rs_556", device_id, now)

        self._service_bypass = self._service_run_holds(conn, now)
        if self._service_bypass:
            self.repo.clear_temp_recover(conn)
        self._load_temperatures(conn, now)
        self._observe_cavitation(conn, gd20, now)
        self._observe_temperatures(conn, gd20, now)
        self._recover_temperature(conn, gd20, now)

        running = None

        if gd20 and int(gd20.get("online") or 0):
            running = bool(int(gd20.get("running") or 0))

        sample = self.repo.read_loop(conn)

        if not sample or sample.get("ts") is None:
            return

        age = (now - sample["ts"]).total_seconds()

        if age < 0 or age > self.loop_max_age_s:
            return

        for channel in self.channels:
            ma = sample.get(f"i{channel}")

            if ma is None:
                continue

            outside = float(ma) < self.loop_low or float(ma) > self.loop_high

            if not outside:
                self._clear(conn, LOOP_RANGE, LOOP_SOURCE, channel, now)
                continue

            alarm = running is True
            self._raise(
                conn,
                {
                    "code": LOOP_RANGE,
                    "source": LOOP_SOURCE,
                    "device_id": channel,
                    "class": "ALARM" if alarm else "WARNING",
                    "message": (
                        f"i{channel} {float(ma):.2f} mA outside "
                        f"{self.loop_low:g}–{self.loop_high:g}"
                    ),
                    "details": {"ma": round(float(ma), 3), "running": running},
                    "latched": 1 if alarm else 0,
                    "inhibit_run": 1 if alarm else 0,
                    "release_policy": "ACK" if alarm else "NONE",
                },
                now,
            )

    def _observe_cavitation(self, conn, gd20, now):

        if not self.cavitation_enabled:
            return

        if not gd20 or not int(gd20.get("online") or 0):
            return

        updated = gd20.get("updated_ts")

        if updated is None:
            return

        age = (now - updated).total_seconds()

        if age < 0 or age > _SAMPLE_MAX_AGE_S:
            return

        device_id = int(gd20.get("device_id") or 0)
        running = bool(int(gd20.get("running") or 0))

        if not running or drive_fault(gd20.get("status_code"), gd20.get("fault_code")):
            self._cavitation_armed = False
            self._cavitation_below_since = None
            self._clear(conn, CAVITATION, "invt_gd20", device_id, now)
            return

        ai2 = gd20.get("ai2_kpa")

        if ai2 is None:
            return

        ai2 = float(ai2)

        if ai2 >= self.cavitation_min_kpa:
            self._cavitation_armed = True
            self._cavitation_below_since = None
            self._clear(conn, CAVITATION, "invt_gd20", device_id, now)
            return

        frequency = gd20.get("frequency_actual_hz")
        at_limit = (
            frequency is not None
            and float(frequency) >= self.cavitation_limit_hz - _LIMIT_TOLERANCE_HZ
        )

        if not self._cavitation_armed:
            if not at_limit:
                return
            since = now - timedelta(seconds=_ARM_LOOKBACK_S)
            if not self.repo.gd20_reached_kpa(conn, device_id, self.cavitation_min_kpa, since):
                return
            self._cavitation_armed = True

        if not at_limit:
            self._cavitation_below_since = None
            return

        if self._cavitation_below_since is None:
            self._cavitation_below_since = now

        held = (now - self._cavitation_below_since).total_seconds()

        if held < self.cavitation_confirm_s:
            return

        current = self.repo.get_state(conn, CAVITATION, "invt_gd20", device_id)

        if current is None and self._generator_is_cold():
            if self._service_bypass:
                return
            if self.repo.arm_temp_recover(conn, now):
                print(
                    f"CAVITATION p_gen_prim_from_frq {ai2:.0f} kPa "
                    f"at {float(frequency):.2f} Hz with cold t_gen_in, STOP"
                )
            self.repo.request_gd20_stop(conn)
            return

        self.repo.clear_temp_recover(conn)
        self._raise(
            conn,
            {
                "code": CAVITATION,
                "source": "invt_gd20",
                "device_id": device_id,
                "class": "ALARM",
                "message": (
                    f"Cavitation: p_gen_prim_from_frq {ai2:.0f} kPa "
                    f"at {float(frequency):.1f} Hz"
                ),
                "details": {
                    "ai2_kpa": round(ai2, 1),
                    "frequency_hz": round(float(frequency), 2),
                    "min_kpa": self.cavitation_min_kpa,
                    "frequency_limit_hz": self.cavitation_limit_hz,
                },
                "latched": 1,
                "inhibit_run": 1,
                "release_policy": "ACK",
            },
            now,
        )

        if self._service_bypass:
            return

        if current is None or not int(current.get("condition_on") or 0):
            print(
                f"CAVITATION p_gen_prim_from_frq {ai2:.0f} kPa "
                f"at {float(frequency):.2f} Hz, STOP"
            )

        self.repo.request_gd20_stop(conn)

    def _load_temperatures(self, conn, now):

        self._temp_values = None

        if not self.temp_enabled:
            return

        row = self.repo.read_temperature(conn)

        if not row or row.get("ts") is None:
            return

        try:
            age = (now - row["ts"]).total_seconds()
        except (TypeError, AttributeError):
            return

        if age < 0 or age > READY_MAX_AGE_S:
            return

        self._temp_values = [row.get(f"t{index}") for index in range(1, 9)]

    def _generator_is_cold(self):

        if self._temp_values is None:
            return False

        return generator_cold(self.temp_channels, self._temp_values)

    def _observe_temperatures(self, conn, gd20, now):

        if not self.temp_enabled:
            return

        if self._temp_values is None:
            self._cond_high_since = None
            self._clear(conn, T_GEN_LOW, TEMP_SOURCE, self._temp_device("t_gen_in"), now)
            self._clear(conn, T_COND_HIGH, TEMP_SOURCE, self._temp_device("t_cond_in"), now)
            return

        gen_id = self._temp_device("t_gen_in")
        cond_id = self._temp_device("t_cond_in")

        if generator_cold(self.temp_channels, self._temp_values):
            _, channel = temperature_channel(self.temp_channels, "t_gen_in")
            value = self._temp_values[gen_id - 1]
            self._raise(
                conn,
                {
                    "code": T_GEN_LOW,
                    "source": TEMP_SOURCE,
                    "device_id": gen_id,
                    "class": "WARNING",
                    "message": (
                        f"t_gen_in {float(value):.1f} °C below {float(channel['ready_min']):g}"
                    ),
                    "details": {"celsius": round(float(value), 1)},
                    "latched": 0,
                    "inhibit_run": 0,
                    "release_policy": "NONE",
                },
                now,
            )
        else:
            self._clear(conn, T_GEN_LOW, TEMP_SOURCE, gen_id, now)

        if condenser_high(self.temp_channels, self._temp_values):
            if self._cond_high_since is None:
                self._cond_high_since = now
            held = (now - self._cond_high_since).total_seconds()
            if held < self.temp_stop_hold_s:
                return
            _, channel = temperature_channel(self.temp_channels, "t_cond_in")
            value = self._temp_values[cond_id - 1]
            self._raise(
                conn,
                {
                    "code": T_COND_HIGH,
                    "source": TEMP_SOURCE,
                    "device_id": cond_id,
                    "class": "WARNING",
                    "message": (
                        f"t_cond_in {float(value):.1f} °C above {float(channel['ready_max']):g}"
                    ),
                    "details": {"celsius": round(float(value), 1)},
                    "latched": 0,
                    "inhibit_run": 0,
                    "release_policy": "NONE",
                },
                now,
            )
            self._stop_for_condenser(conn, gd20, now)
            return

        self._cond_high_since = None
        self._clear(conn, T_COND_HIGH, TEMP_SOURCE, cond_id, now)

    def _temp_device(self, name):

        index, _channel = temperature_channel(self.temp_channels, name)
        return 0 if index is None else index

    def _service_run_holds(self, conn, now):

        command = self.repo.read_run_command(conn)
        service = self.repo.read_service(conn)

        if (
            not command
            or str(command.get("value")) != "1"
            or command.get("source") != RUN_SOURCE
        ):
            return False

        if not service:
            return False

        return service_is_fresh(
            service.get("value"),
            service.get("updated_ts"),
            now,
            self.service_idle_s,
        )

    def _stop_for_condenser(self, conn, gd20, now):

        if self._service_bypass:
            return

        if not gd20 or not int(gd20.get("online") or 0):
            return

        if not int(gd20.get("running") or 0):
            return

        if int(gd20.get("external_stop") or 0):
            return

        if drive_fault(gd20.get("status_code"), gd20.get("fault_code")):
            return

        if self.repo.get_state(conn, CAVITATION, "invt_gd20", int(gd20.get("device_id") or 0)) is None:
            if self.repo.arm_temp_recover(conn, now):
                print("t_cond_in high, STOP, temperature recovery")

        self.repo.request_gd20_stop(conn)

    def _recover_temperature(self, conn, gd20, now):

        if self._service_bypass or not self.temp_enabled:
            return

        recover = self.repo.read_temp_recover(conn)

        if not recover or not int(recover.get("armed") or 0):
            return

        if self._cancel_temp_recover(conn, gd20, recover):
            self.repo.clear_temp_recover(conn)
            return

        if not gd20 or not int(gd20.get("online") or 0):
            return

        if int(gd20.get("running") or 0):
            command = self.repo.read_run_command(conn)
            if (
                command
                and str(command.get("value")) == "1"
                and command.get("source") == "temperature"
            ):
                self.repo.clear_temp_recover(conn)
            return

        if self.repo.any_blocking(conn):
            return

        try:
            allowed = self._start_permitted(conn, now)
        except Exception as e:
            print("temperature recovery:", e)
            return

        if not allowed:
            return

        self.repo.request_gd20_run(conn)
        print("GD20 RUN temperature recovery")

    def _cancel_temp_recover(self, conn, gd20, recover):

        if gd20 and int(gd20.get("online") or 0):
            if int(gd20.get("external_stop") or 0):
                return True
            if drive_fault(gd20.get("status_code"), gd20.get("fault_code")):
                return True

        device_id = int((gd20 or {}).get("device_id") or 0)
        if device_id and self.repo.get_state(conn, CAVITATION, "invt_gd20", device_id):
            return True

        command = self.repo.read_run_command(conn)
        armed_ts = recover.get("updated_ts")

        if (
            command
            and str(command.get("value")) == "0"
            and command.get("source") == "hmi"
            and armed_ts is not None
            and command.get("updated_ts") is not None
            and command["updated_ts"] > armed_ts
        ):
            return True

        return False

    def _start_permitted(self, conn, now):

        if self.start_check is not None:
            return bool(self.start_check())

        return start_allowed(conn, load_config(), now)

    def acknowledge(self, conn, code, source, device_id, now, ack_source="hmi"):

        device_id = int(device_id)
        current = self.repo.get_state(conn, code, source, device_id)

        if current is None:
            return False

        if current.get("ack_ts") is None:
            current["ack_ts"] = now
            current["ack_source"] = ack_source
            self.repo.save_state(conn, current)
            self.repo.update_event(conn, current["event_id"], {"ack_ts": now})

        if not int(current["condition_on"]):
            self._close(conn, current, now)

        return True

    def blocks(self, conn):

        return bool(self.repo.any_blocking(conn))

    def open_rows(self, conn):

        return list(self.repo.list_state(conn))

    def _raise(self, conn, spec, now):

        current = self.repo.get_state(
            conn, spec["code"], spec["source"], int(spec["device_id"])
        )

        if (
            current is not None
            and current["class"] == "ALARM"
            and int(current["latched"])
            and spec["class"] == "WARNING"
        ):
            spec = dict(spec)
            spec["class"] = "ALARM"
            spec["latched"] = 1
            spec["inhibit_run"] = current["inhibit_run"]
            spec["release_policy"] = current["release_policy"]

        details = _details(spec.get("details"))
        event = {
            "code": spec["code"],
            "source": spec["source"],
            "device_id": int(spec["device_id"]),
            "class": spec["class"],
            "message": spec["message"],
            "details": details,
            "inhibit_run": int(spec["inhibit_run"]),
            "release_policy": spec["release_policy"],
        }

        if current is None:
            event_id = self.repo.insert_event(
                conn,
                dict(event, ts=now, ack_ts=None, cleared_ts=None),
            )
            self.repo.save_state(
                conn,
                dict(
                    event,
                    condition_on=1,
                    latched=int(spec["latched"]),
                    event_id=event_id,
                    raised_ts=now,
                    ack_ts=None,
                    ack_source=None,
                    cleared_ts=None,
                ),
            )
            self._notify_alarm(event, now)
            return

        was_alarm = current["class"] == "ALARM"
        self.repo.update_event(conn, current["event_id"], event)
        current.update(event)
        current["condition_on"] = 1
        current["latched"] = int(spec["latched"]) or int(current["latched"])
        self.repo.save_state(conn, current)

        if not was_alarm:
            self._notify_alarm(event, now)

    def _notify_alarm(self, event, now):

        if self.notifier is None or event.get("class") != "ALARM":
            return

        try:
            self.notifier(dict(event, ts=now))
        except Exception as exc:
            print("alarm mail:", exc)

    def _clear(self, conn, code, source, device_id, now):

        current = self.repo.get_state(conn, code, source, int(device_id))

        if current is None:
            return

        latched = current["class"] == "ALARM" and int(current["latched"])

        if not latched:
            self._close(conn, current, now)
            return

        if int(current["condition_on"]):
            current["condition_on"] = 0
            self.repo.save_state(conn, current)

        if current.get("ack_ts") is not None:
            self._close(conn, current, now)

    def _close(self, conn, current, now):

        self.repo.update_event(conn, current["event_id"], {"cleared_ts": now})
        self.repo.delete_state(
            conn, current["code"], current["source"], int(current["device_id"])
        )


class SqlRepo:

    def _cursor(self, conn):

        return conn.cursor(DictCursor)

    def get_link(self, conn, source, device_id):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT source, device_id, online, fail_streak, last_ok_ts, last_fail_ts
                FROM device_link
                WHERE source = %s AND device_id = %s
                """,
                (source, int(device_id)),
            )
            return cur.fetchone()

    def save_link(self, conn, row):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO device_link
                    (source, device_id, online, fail_streak, last_ok_ts, last_fail_ts)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    online = VALUES(online),
                    fail_streak = VALUES(fail_streak),
                    last_ok_ts = VALUES(last_ok_ts),
                    last_fail_ts = VALUES(last_fail_ts)
                """,
                (
                    row["source"],
                    int(row["device_id"]),
                    int(row["online"]),
                    int(row["fail_streak"]),
                    row.get("last_ok_ts"),
                    row.get("last_fail_ts"),
                ),
            )

    def get_state(self, conn, code, source, device_id):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT code, source, device_id, class, message, details,
                       condition_on, latched, inhibit_run, release_policy,
                       event_id, raised_ts, ack_ts, ack_source, cleared_ts
                FROM alarm_state
                WHERE code = %s AND source = %s AND device_id = %s
                """,
                (code, source, int(device_id)),
            )
            return cur.fetchone()

    def save_state(self, conn, row):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO alarm_state
                    (code, source, device_id, class, message, details,
                     condition_on, latched, inhibit_run, release_policy,
                     event_id, raised_ts, ack_ts, ack_source, cleared_ts)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    class = VALUES(class),
                    message = VALUES(message),
                    details = VALUES(details),
                    condition_on = VALUES(condition_on),
                    latched = VALUES(latched),
                    inhibit_run = VALUES(inhibit_run),
                    release_policy = VALUES(release_policy),
                    event_id = VALUES(event_id),
                    ack_ts = VALUES(ack_ts),
                    ack_source = VALUES(ack_source),
                    cleared_ts = VALUES(cleared_ts)
                """,
                (
                    row["code"],
                    row["source"],
                    int(row["device_id"]),
                    row["class"],
                    row["message"],
                    row.get("details"),
                    int(row["condition_on"]),
                    int(row["latched"]),
                    int(row["inhibit_run"]),
                    row["release_policy"],
                    row.get("event_id"),
                    row.get("raised_ts"),
                    row.get("ack_ts"),
                    row.get("ack_source"),
                    row.get("cleared_ts"),
                ),
            )

    def delete_state(self, conn, code, source, device_id):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                DELETE FROM alarm_state
                WHERE code = %s AND source = %s AND device_id = %s
                """,
                (code, source, int(device_id)),
            )

    def insert_event(self, conn, row):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO alarm_event
                    (ts, code, source, device_id, class, message, details,
                     inhibit_run, release_policy, ack_ts, cleared_ts)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row["ts"],
                    row["code"],
                    row["source"],
                    int(row["device_id"]),
                    row["class"],
                    row["message"],
                    row.get("details"),
                    int(row["inhibit_run"]),
                    row["release_policy"],
                    row.get("ack_ts"),
                    row.get("cleared_ts"),
                ),
            )
            return int(cur.lastrowid)

    def update_event(self, conn, event_id, fields):

        if not event_id or not fields:
            return

        allowed = {
            "class",
            "message",
            "details",
            "inhibit_run",
            "release_policy",
            "ack_ts",
            "cleared_ts",
        }
        keys = [key for key in fields if key in allowed]

        if not keys:
            return

        assignments = ", ".join(f"{key} = %s" for key in keys)
        params = [fields[key] for key in keys]
        params.append(int(event_id))

        with self._cursor(conn) as cur:
            cur.execute(
                f"UPDATE alarm_event SET {assignments} WHERE id = %s",
                params,
            )

    def any_blocking(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT 1 AS blocked
                FROM alarm_state
                WHERE inhibit_run = 1
                  AND (ack_ts IS NULL OR condition_on = 1)
                LIMIT 1
                """
            )
            return cur.fetchone() is not None

    def list_state(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT code, source, device_id, class, message, details,
                       condition_on, latched, inhibit_run, release_policy,
                       raised_ts, ack_ts
                FROM alarm_state
                ORDER BY class, raised_ts
                """
            )
            return cur.fetchall()

    def read_gd20(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT device_id, online, running, status_code, fault_code,
                       external_stop, ai2_kpa, frequency_actual_hz, updated_ts
                FROM invt_gd20_state
                ORDER BY device_id
                LIMIT 1
                """
            )
            return cur.fetchone()

    def gd20_reached_kpa(self, conn, device_id, min_kpa, since):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT 1 AS reached
                FROM invt_gd20
                WHERE device_id = %s
                  AND running = 1
                  AND ai2_kpa >= %s
                  AND ts >= %s
                LIMIT 1
                """,
                (int(device_id), float(min_kpa), since),
            )
            return cur.fetchone() is not None

    def read_temperature(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT ts, t1, t2, t3, t4, t5, t6, t7, t8
                FROM temperature
                ORDER BY id DESC
                LIMIT 1
                """
            )
            return cur.fetchone()

    def read_run_command(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT value, source, updated_ts
                FROM control_state
                WHERE parameter = 'gd20_run'
                """
            )
            return cur.fetchone()

    def read_service(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT value, updated_ts
                FROM control_state
                WHERE parameter = 'hmi_service'
                """
            )
            return cur.fetchone()

    def read_temp_recover(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT value, updated_ts
                FROM control_state
                WHERE parameter = 'gd20_temp_recover'
                """
            )
            row = cur.fetchone()

        if row is None:
            return None

        return {"armed": 1 if str(row["value"]) == "1" else 0, "updated_ts": row["updated_ts"]}

    def arm_temp_recover(self, conn, now):

        current = self.read_temp_recover(conn)

        if current and int(current["armed"]):
            return False

        with self._cursor(conn) as cur:
            cur.execute(
                """
                REPLACE INTO control_state (parameter, value, source, updated_ts)
                VALUES ('gd20_temp_recover', '1', 'temperature', %s)
                """,
                (now,),
            )
        return True

    def clear_temp_recover(self, conn):

        current = self.read_temp_recover(conn)

        if not current or not int(current["armed"]):
            return

        with self._cursor(conn) as cur:
            cur.execute(
                """
                REPLACE INTO control_state (parameter, value, source)
                VALUES ('gd20_temp_recover', '0', 'temperature')
                """
            )

    def request_gd20_run(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO control (parameter, value, source)
                VALUES ('gd20_run', '1', 'temperature')
                """
            )
            cur.execute(
                """
                REPLACE INTO control_state (parameter, value, source)
                VALUES ('gd20_run', '1', 'temperature')
                """
            )

    def request_gd20_stop(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO control (parameter, value, source)
                VALUES ('gd20_run', '0', 'alarm')
                """
            )
            cur.execute(
                """
                REPLACE INTO control_state (parameter, value, source)
                VALUES ('gd20_run', '0', 'alarm')
                """
            )

    def read_em2rs(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT device_id, online, alarm, alarm_text
                FROM em2rs_556_state
                ORDER BY device_id
                LIMIT 1
                """
            )
            return cur.fetchone()

    def read_loop(self, conn):

        with self._cursor(conn) as cur:
            cur.execute(
                """
                SELECT ts, i6, i7, i8
                FROM current_loop
                ORDER BY id DESC
                LIMIT 1
                """
            )
            return cur.fetchone()
