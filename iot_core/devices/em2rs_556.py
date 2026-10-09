import time

from iot_core.devices.base_device import BaseDevice
from iot_core.modbus.compat import call_with_fallback


# Path 0 je súvislý blok Pr9.00..Pr9.06. Manuál EM2RS V1.5, adresy 0x6200–0x6206.
_PATH0_ADDRESS = 0x6200
_PATH0_COUNT = 7
_PATH0_FIELDS = (
    "path0_mode",
    "target_position_high",
    "target_position_low",
    "speed",
    "acceleration",
    "deceleration",
    "pause_time",
)

# Príkazový register a riadiace slovo EEPROM/reset sa pri setupe nezapisujú.
_SETUP_FORBIDDEN = frozenset({0x6002, 0x1801})


_RUNNING_BIT = 0x0004
_ABSOLUTE_MODE = 0x0001
_RELATIVE_MODE = 0x0041


def words_to_int32(high_word, low_word):

    raw = ((int(high_word) & 0xFFFF) << 16) | (int(low_word) & 0xFFFF)

    if raw >= 0x80000000:
        raw -= 0x100000000

    return raw


def split_int32(value):

    raw = int(value) & 0xFFFFFFFF

    return (raw >> 16) & 0xFFFF, raw & 0xFFFF


def motion_limit_s(valve, motion):

    steps = int(valve["homing_steps"])
    ppr = int(valve["pulses_per_revolution"])
    rpm = float(motion["default_speed_rpm"])

    if steps < 0 or ppr <= 0 or rpm <= 0:
        return None

    return steps / ppr / rpm * 60.0


def percent_to_steps(percent, full_travel_steps):

    full = int(full_travel_steps)
    steps = int(round(float(percent) * full / 100.0))

    if steps < 0:
        return 0

    if steps > full:
        return full

    return steps


def homing_delta(valve):

    steps = int(valve["homing_steps"])

    if str(valve.get("homing_direction", "CLOSE")).upper() == "CLOSE":
        return -steps

    return steps


def judge_word(expected, actual, read_error):

    if read_error:
        return "READ_ERROR", read_error

    if expected is None:
        return "MANUAL_APPROVAL_REQUIRED", "expected is null; a successful read is not a match"

    if actual == expected:
        return "MATCH", "value matches the expected register word"

    return "DIFFERENT", "value differs from the expected register word"


def overall_status(items):

    results = [item["result"] for item in items]

    if any(result == "READ_ERROR" for result in results):
        return "CONFIG_READ_ERROR"

    if any(result == "DIFFERENT" for result in results):
        return "CONFIG_MISMATCH"

    if any(item["expected"] is None or item["result"] == "UNSUPPORTED" for item in items):
        return "CONFIG_NOT_CHECKED"

    if items and all(result == "MATCH" for result in results):
        return "CONFIG_MATCH"

    return "CONFIG_NOT_CHECKED"


def _read_holding(client, address, count, slave_id):

    rr = call_with_fallback(
        client.read_holding_registers,
        address=address,
        count=count,
        unit_id=slave_id,
    )

    if not rr or (hasattr(rr, "isError") and rr.isError()):
        return None

    if not hasattr(rr, "registers") or len(rr.registers) != count:
        return None

    return [int(word) & 0xFFFF for word in rr.registers]


class Em2rs556Device(BaseDevice):

    def __init__(self, slave_id, device_cfg):

        super().__init__(slave_id)

        self.device_cfg = device_cfg
        self.registers = (device_cfg.get("modbus") or {}).get("registers") or {}
        self.parameters = (device_cfg.get("startup_check") or {}).get("parameters") or {}
        self.frame_delay_s = 0.03
        self.motion_phase = "IDLE"
        self.position_valid = False
        self.alarm = False
        self.alarm_text = None
        self.hmi_mode = "MANUAL"
        self.requested_position_pct = None
        self.requested_position_steps = None
        self.actual_position_steps = None
        self.expected_delta_steps = None
        self.actual_delta_steps = None
        self.position_check = None
        self.running = False
        self._move_started = None
        self._start_steps = None
        self._target_steps = None
        self._requests_seeded = False
        self._seen = {}
        self._state_loaded = False
        self._enable_on = None
        self._io_enable_released = False

    def execute(self, client, db_conn, ts):

        try:
            snapshot = self._read_snapshot(client)
        except Exception as e:
            print("EM2RS Modbus call failed:", e)
            self._set_offline(db_conn)
            return

        if snapshot is None:
            print("EM2RS OFFLINE")
            self._set_offline(db_conn)
            return

        items = self._check_items(snapshot)
        status = overall_status(items)

        print(
            "EM2RS",
            f"ts={ts}",
            f"status={status}",
            f"pr0={_actual_expected(items, 'pulse_per_revolution')}",
            f"pr5={_actual_expected(items, 'peak_current')}",
            f"mode={snapshot.get('path0_mode')}",
            f"pos={snapshot.get('target_position')}",
            f"speed={_actual_expected(items, 'path0_speed')}",
            f"acc={_actual_expected(items, 'path0_acceleration')}",
            f"dec={_actual_expected(items, 'path0_deceleration')}",
            f"pause={snapshot.get('pause_time')}",
        )

        try:
            running = self._read_running(client)
            actual_steps = self._read_actual_steps(client)
            self._poll_motion(client, db_conn, running, actual_steps)
        except Exception as e:
            print("EM2RS motion error:", e)

        try:
            self._upsert_state(db_conn, snapshot, status, ts)
        except Exception as e:
            print("EM2RS DB error:", e)

    def apply_setup(self, client, frame_delay_s=0.03):

        """Raz pri štarte mastera. Zapíše len expected slová, ktoré sa líšia."""

        results = []

        for name, spec in self.parameters.items():

            if not isinstance(spec, dict):
                results.append(_setup_result(name, None, None, None, "SKIP", "parameter definition is not a mapping"))
                continue

            register = spec.get("register") or ""
            expected, expected_error = _expected_word(spec.get("expected"))

            if expected_error or expected is None:
                results.append(_setup_result(name, register, None, expected, "SKIP", expected_error or "expected is null"))
                continue

            address = self._address(register)

            if address is None or address in _SETUP_FORBIDDEN:
                results.append(_setup_result(name, register, address, expected, "SKIP", "address is not a setup register"))
                continue

            actual = _read_word(client, address, self.slave_id)

            if actual is None:
                results.append(_setup_result(name, register, address, expected, "READ_ERROR", "FC03 returned no word"))
                print(f"EM2RS setup {name} 0x{address:04X} read failed")
                continue

            if actual == expected:
                results.append(_setup_result(name, register, address, expected, "SKIP", "already matches", actual))
                print(f"EM2RS setup {name} 0x{address:04X} {actual} == {expected}")
                continue

            if frame_delay_s:
                time.sleep(frame_delay_s)

            if not _write_register(client, address, expected, self.slave_id):
                results.append(_setup_result(name, register, address, expected, "WRITE_FAILED", "FC06 failed", actual))
                print(f"EM2RS setup {name} 0x{address:04X} {actual} -> {expected} WRITE_FAILED")
                continue

            if frame_delay_s:
                time.sleep(frame_delay_s)

            checked = _read_word(client, address, self.slave_id)

            if checked != expected:
                results.append(_setup_result(name, register, address, expected, "VERIFY_FAILED", "read-back differs", checked))
                print(f"EM2RS setup {name} 0x{address:04X} read-back {checked} != {expected}")
                continue

            results.append(_setup_result(name, register, address, expected, "WROTE", "written and verified", checked))
            print(f"EM2RS setup {name} 0x{address:04X} {actual} -> {expected}")

        self.frame_delay_s = frame_delay_s
        self._release_io_enable(client)
        self._set_enable(client, False)

        return results

    def _read_snapshot(self, client):

        path = _read_holding(client, _PATH0_ADDRESS, _PATH0_COUNT, self.slave_id)
        singles = {}
        any_word = path is not None

        for key in ("pulse_per_revolution", "peak_current"):
            address = self._address(key)
            if address is None:
                singles[key] = None
                continue
            words = _read_holding(client, address, 1, self.slave_id)
            singles[key] = None if words is None else words[0]
            any_word = any_word or words is not None

        if not any_word:
            return None

        snapshot = {
            "pulse_per_revolution": singles.get("pulse_per_revolution"),
            "peak_current": singles.get("peak_current"),
        }

        if path is None:
            for field in _PATH0_FIELDS:
                snapshot[field] = None
            snapshot["target_position"] = None
            return snapshot

        for field, word in zip(_PATH0_FIELDS, path):
            snapshot[field] = word

        snapshot["target_position"] = words_to_int32(path[1], path[2])
        return snapshot

    def _check_items(self, snapshot):

        items = []

        for name, spec in self.parameters.items():

            if not isinstance(spec, dict):
                items.append(_item(name, None, None, None, "UNSUPPORTED", "parameter definition is not a mapping"))
                continue

            register = spec.get("register") or ""
            policy = spec.get("policy") or ""
            expected, expected_error = _expected_word(spec.get("expected"))

            if policy != "check_only":
                items.append(_item(name, register, None, None, "UNSUPPORTED", "policy is not check_only"))
                continue

            if expected_error:
                items.append(_item(name, register, None, None, "UNSUPPORTED", expected_error))
                continue

            actual_key = register
            if actual_key not in snapshot:
                items.append(_item(name, register, expected, None, "UNSUPPORTED", "register is not in the EM2RS map"))
                continue

            actual = snapshot.get(actual_key)
            read_error = None if actual is not None else "FC03 returned no word"
            result, reason = judge_word(expected, actual, read_error)
            items.append(_item(name, register, expected, actual, result, reason))

        return items

    def _address(self, register_key):

        mapped = self.registers.get(register_key)

        if not isinstance(mapped, dict) or "address" not in mapped:
            return None

        address = mapped["address"]

        if isinstance(address, bool) or not isinstance(address, int):
            return None

        if address < 0 or address > 65535:
            return None

        return address

    def _set_offline(self, db_conn):

        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE em2rs_556_state
                    SET online = 0
                    WHERE device_id = %s
                    """,
                    (self.slave_id,),
                )
        except Exception as e:
            print("EM2RS offline write error:", e)

    def _poll_motion(self, client, db_conn, running, actual_steps):

        self._load_state(db_conn)
        self.running = running is True
        self.actual_position_steps = actual_steps

        if running is None:
            return

        limit = motion_limit_s(self.device_cfg["valve"], self.device_cfg["motion"])
        steps = int(self.device_cfg["valve"]["homing_steps"])

        if self.motion_phase in ("HOMING_MOVE", "POSITION_MOVE", "HOMING_ZERO") and running:
            if (
                self._move_started is not None
                and limit is not None
                and time.monotonic() - self._move_started > limit
            ):
                self._trip_timeout(client, limit, steps)
            return

        if self.motion_phase == "HOMING_MOVE" and not running:
            self._finish_homing_move(client, actual_steps)
            return

        if self.motion_phase == "HOMING_ZERO" and not running:
            self._finish_homing_zero(client, actual_steps)
            return

        if self.motion_phase == "POSITION_MOVE" and not running:
            self._finish_position(client, actual_steps)
            return

        if self.motion_phase == "ALARM":
            if running:
                self._quick_stop(client)
            else:
                self._set_enable(client, False)
                self._maybe_reset_alarm(db_conn)
            return

        if running:
            if self._move_started is None:
                self._move_started = time.monotonic()
            elif limit is not None and time.monotonic() - self._move_started > limit:
                self._trip_timeout(client, limit, steps)
            return

        self._accept_requests(client, db_conn, actual_steps)

        if self.motion_phase == "IDLE":
            self._set_enable(client, False)

    def _trip_timeout(self, client, limit, steps):

        self._quick_stop(client)
        self.alarm = True
        self.alarm_text = f"beh dlhší ako {limit:.1f} s pre {steps} pulzov"
        self.motion_phase = "ALARM"
        self.position_check = "TIMEOUT"
        print("EM2RS", self.alarm_text)

    def _finish_homing_move(self, client, actual_steps):

        if actual_steps is None or self._start_steps is None:
            self._latch_alarm("chýba počítadlo po homingu")
            self._set_enable(client, False)
            return

        got = actual_steps - self._start_steps
        self.expected_delta_steps = homing_delta(self.device_cfg["valve"])
        self.actual_delta_steps = got

        if got != self.expected_delta_steps:
            self.position_check = "DIFFERENT"
            self._latch_alarm(
                f"homing očakával {self.expected_delta_steps} pulzov, počítadlo {got}"
            )
            self._set_enable(client, False)
            return

        self.position_check = "MATCH"
        self._write_register_pause(client, self._address("command"), self._command("set_current_position_zero"))
        self.motion_phase = "HOMING_ZERO"
        self._move_started = time.monotonic()
        print("EM2RS homing move ok, zero counter")

    def _finish_homing_zero(self, client, actual_steps):

        self.actual_position_steps = actual_steps

        if actual_steps == 0:
            self.position_valid = True
            self._write_register_pause(client, self._address("path0_mode"), _ABSOLUTE_MODE)
            self.motion_phase = "IDLE"
            self.position_check = "MATCH"
            self.expected_delta_steps = 0
            self.actual_delta_steps = 0
            self.requested_position_steps = 0
            self.requested_position_pct = 0
            self._set_enable(client, False)
            print("EM2RS homing zero ok")
            return

        self._latch_alarm("počítadlo po homingu nie je 0")
        self._set_enable(client, False)

    def _finish_position(self, client, actual_steps):

        if actual_steps is None or self._start_steps is None or self._target_steps is None:
            self._latch_alarm("chýba počítadlo po posune")
            self._set_enable(client, False)
            return

        expected = self._target_steps - self._start_steps
        got = actual_steps - self._start_steps
        self.expected_delta_steps = expected
        self.actual_delta_steps = got
        self.requested_position_steps = self._target_steps

        if actual_steps == self._target_steps:
            self.position_check = "MATCH"
            self.motion_phase = "IDLE"
            self._set_enable(client, False)
            print(f"EM2RS position {self._target_steps} ok")
            return

        self.position_check = "DIFFERENT"
        self._latch_alarm(f"očakávaný posun {expected}, skutočný {got}")
        self._set_enable(client, False)

    def _accept_requests(self, client, db_conn, actual_steps):

        rows = {
            name: self._control_row(db_conn, name)
            for name in ("em2rs_mode", "em2rs_homing", "em2rs_position_pct", "em2rs_alarm_reset")
        }

        if not self._requests_seeded:
            self._seen = {name: None if row is None else row[1] for name, row in rows.items()}
            self._requests_seeded = True
            return

        mode_row = rows["em2rs_mode"]
        if mode_row is not None and mode_row[1] != self._seen.get("em2rs_mode"):
            self._seen["em2rs_mode"] = mode_row[1]
            mode = str(mode_row[0]).strip().upper()
            if mode in ("MANUAL", "AUTO"):
                self.hmi_mode = mode

        reset_row = rows["em2rs_alarm_reset"]
        if reset_row is not None and reset_row[1] != self._seen.get("em2rs_alarm_reset"):
            self._seen["em2rs_alarm_reset"] = reset_row[1]
            if self.alarm and not self.running:
                self.alarm = False
                self.alarm_text = None
                self.motion_phase = "IDLE"
                self.position_check = None

        if self.alarm or self.hmi_mode != "MANUAL":
            return

        homing_row = rows["em2rs_homing"]
        if homing_row is not None and homing_row[1] != self._seen.get("em2rs_homing"):
            self._seen["em2rs_homing"] = homing_row[1]
            self._start_homing(client, actual_steps)
            return

        position_row = rows["em2rs_position_pct"]
        if position_row is not None and position_row[1] != self._seen.get("em2rs_position_pct"):
            self._seen["em2rs_position_pct"] = position_row[1]
            self._start_position(client, actual_steps, position_row[0])

    def _motion_allowed(self):

        return bool((self.device_cfg.get("safety") or {}).get("motion_writes_enabled"))

    def _load_state(self, db_conn):

        if self._state_loaded:
            return

        self._state_loaded = True

        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT mode, alarm, alarm_text, motion_phase, position_valid,
                           requested_position_pct, requested_position_steps
                    FROM em2rs_556_state
                    WHERE device_id = %s
                    """,
                    (self.slave_id,),
                )
                row = cur.fetchone()
        except Exception as e:
            print("EM2RS state load:", e)
            return

        if not row:
            return

        mode, alarm, text, phase, valid, pct, steps = row[:7]

        if mode in ("MANUAL", "AUTO"):
            self.hmi_mode = mode

        self.position_valid = bool(valid)
        self.requested_position_pct = pct
        self.requested_position_steps = steps

        if alarm:
            self.alarm = True
            self.alarm_text = text
            self.motion_phase = "ALARM"
            return

        if phase in ("HOMING_MOVE", "HOMING_ZERO", "POSITION_MOVE"):
            self.alarm = True
            self.alarm_text = "pohyb prerušený reštartom"
            self.motion_phase = "ALARM"

    def _start_homing(self, client, actual_steps):

        if not self._motion_allowed():
            print("EM2RS homing refused, motion writes disabled")
            return

        if self.running or actual_steps is None:
            print("EM2RS homing refused, driver running or counter missing")
            return

        self.alarm_text = None

        delta = homing_delta(self.device_cfg["valve"])
        high, low = split_int32(delta)
        self._start_steps = actual_steps
        self._target_steps = None
        self.expected_delta_steps = delta
        self.requested_position_pct = None
        self.requested_position_steps = None
        self._write_register_pause(client, self._address("path0_mode"), _RELATIVE_MODE)
        self._write_register_pause(client, self._address("target_position_high"), high)
        self._write_register_pause(client, self._address("target_position_low"), low)
        self._set_enable(client, True)
        self._write_register_pause(client, self._address("command"), self._command("start_path_0"))
        self.motion_phase = "HOMING_MOVE"
        self._move_started = time.monotonic()
        print(f"EM2RS homing start {delta} pulses")

    def _start_position(self, client, actual_steps, raw_percent):

        if not self._motion_allowed():
            print("EM2RS position refused, motion writes disabled")
            return

        if not self.position_valid:
            self.alarm_text = "najprv homing"
            print("EM2RS position refused, homing required")
            return

        if self.running or actual_steps is None:
            print("EM2RS position refused, driver running or counter missing")
            return

        try:
            percent = float(str(raw_percent).strip())
        except ValueError:
            return

        full = int(self.device_cfg["valve"]["full_travel_steps"])
        if percent < 0 or percent > 100:
            return

        target = percent_to_steps(percent, full)
        high, low = split_int32(target)
        self._start_steps = actual_steps
        self._target_steps = target
        self.requested_position_pct = percent
        self.requested_position_steps = target
        self.expected_delta_steps = target - actual_steps
        self._write_register_pause(client, self._address("path0_mode"), _ABSOLUTE_MODE)
        self._write_register_pause(client, self._address("target_position_high"), high)
        self._write_register_pause(client, self._address("target_position_low"), low)
        self._set_enable(client, True)
        self._write_register_pause(client, self._address("command"), self._command("start_path_0"))
        self.motion_phase = "POSITION_MOVE"
        self._move_started = time.monotonic()
        print(f"EM2RS position start {percent:g}% -> {target}")

    def _maybe_reset_alarm(self, db_conn):

        row = self._control_row(db_conn, "em2rs_alarm_reset")
        if row is None or row[1] == self._seen.get("em2rs_alarm_reset"):
            return
        self._seen["em2rs_alarm_reset"] = row[1]
        self.alarm = False
        self.alarm_text = None
        self.motion_phase = "IDLE"
        self.position_check = None

    def _latch_alarm(self, text):

        self.alarm = True
        self.alarm_text = text
        self.motion_phase = "ALARM"
        print("EM2RS", text)

    def _quick_stop(self, client):

        self._write_register_pause(client, self._address("command"), self._command("quick_stop"))

    def _release_io_enable(self, client):

        if self._io_enable_released:
            return

        address = self._address("si1")
        if address is None:
            return

        actual = _read_word(client, address, self.slave_id)
        if actual is None:
            return

        self._io_enable_released = True
        if actual == 0:
            print("EM2RS SI1 0x0145 0, DI1 neriadi enable")
            return

        if self._write_register_pause(client, address, 0):
            print(f"EM2RS SI1 0x0145 {actual} -> 0, DI1 už neriadi enable")
            return

        self._io_enable_released = False
        print("EM2RS SI1 write failed")

    def _set_enable(self, client, on):

        if self._enable_on is on:
            return True

        address = self._address("forced_enable")
        if address is None:
            return False

        value = 1 if on else 0

        if self._enable_on is None and not on:
            actual = _read_word(client, address, self.slave_id)
            if actual is None:
                return False
            if actual == 0:
                self._enable_on = False
                return True
        if not self._write_register_pause(client, address, value):
            print("EM2RS enable write failed")
            return False

        self._enable_on = on
        print("EM2RS enable", "on" if on else "off")
        return True

    def _write_register_pause(self, client, address, value):

        if address is None or value is None:
            return False

        if self.frame_delay_s:
            time.sleep(self.frame_delay_s)

        ok = _write_register(client, address, int(value), self.slave_id)

        if self.frame_delay_s:
            time.sleep(self.frame_delay_s)

        return ok

    def _command(self, key):

        commands = (self.device_cfg.get("modbus") or {}).get("commands") or {}
        return int(commands[key])

    def _read_running(self, client):

        address = self._address("motion_status")
        if address is None:
            return None
        word = _read_word(client, address, self.slave_id)
        if word is None:
            return None
        return bool(word & _RUNNING_BIT)

    def _read_actual_steps(self, client):

        address = self._address("actual_position_high")
        if address is None:
            return None
        words = _read_holding(client, address, 2, self.slave_id)
        if words is None:
            return None
        return words_to_int32(words[0], words[1])

    def _control_row(self, db_conn, name):

        with db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT value, updated_ts
                FROM control_state
                WHERE parameter = %s
                """,
                (name,),
            )
            return cur.fetchone()

    def _upsert_state(self, db_conn, snapshot, status, ts):

        peak_raw = snapshot.get("peak_current")
        scale = float((self.registers.get("peak_current") or {}).get("scale", 0.1))
        peak_a = None if peak_raw is None else peak_raw * scale

        columns = [
            "device_id",
            "online",
            "config_status",
            "pulse_per_revolution",
            "peak_current_raw",
            "peak_current_a",
            "path0_mode",
            "target_position",
            "speed_rpm",
            "acceleration",
            "deceleration",
            "pause_time",
            "mode",
            "requested_position_pct",
            "requested_position_steps",
            "actual_position_steps",
            "expected_delta_steps",
            "actual_delta_steps",
            "position_check",
            "running",
            "alarm",
            "alarm_text",
            "motion_phase",
            "position_valid",
        ]
        params = [
            self.slave_id,
            1,
            status,
            snapshot.get("pulse_per_revolution"),
            peak_raw,
            peak_a,
            snapshot.get("path0_mode"),
            snapshot.get("target_position"),
            snapshot.get("speed"),
            snapshot.get("acceleration"),
            snapshot.get("deceleration"),
            snapshot.get("pause_time"),
            self.hmi_mode,
            self.requested_position_pct,
            self.requested_position_steps,
            self.actual_position_steps,
            self.expected_delta_steps,
            self.actual_delta_steps,
            self.position_check,
            1 if self.running else 0,
            1 if self.alarm else 0,
            self.alarm_text,
            self.motion_phase,
            1 if self.position_valid else 0,
        ]
        assignments = ", ".join(
            f"{column} = VALUES({column})" for column in columns if column != "device_id"
        )
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"""
            INSERT INTO em2rs_556_state ({", ".join(columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {assignments}
        """

        full = int(self.device_cfg["valve"]["full_travel_steps"])
        actual_pct = None
        if self.actual_position_steps is not None and full:
            actual_pct = self.actual_position_steps * 100.0 / full

        with db_conn.cursor() as cur:
            cur.execute(sql, params)
            cur.execute(
                """
                INSERT INTO em2rs_556
                    (ts, device_id, mode, requested_position_steps, actual_position_steps,
                     running, alarm, position_check)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ts,
                    self.slave_id,
                    self.hmi_mode,
                    self.requested_position_steps,
                    self.actual_position_steps,
                    1 if self.running else 0,
                    1 if self.alarm else 0,
                    self.position_check,
                ),
            )

        self._actual_position_pct = actual_pct


def _expected_word(raw):

    if raw is None:
        return None, None

    if isinstance(raw, bool) or not isinstance(raw, int):
        return None, "expected must be an integer register word or null"

    if raw < 0 or raw > 65535:
        return None, "expected is outside a 16-bit register word"

    return raw, None


def _read_word(client, address, slave_id):

    words = _read_holding(client, address, 1, slave_id)

    if words is None:
        return None

    return words[0]


def _write_register(client, address, value, slave_id):

    fn = client.write_register
    tries = [
        lambda: fn(address=address, value=value, device_id=slave_id),
        lambda: fn(address=address, value=value, unit=slave_id),
        lambda: fn(address=address, value=value, slave=slave_id),
        lambda: fn(address, value, slave_id),
    ]
    last = None

    for attempt in tries:
        try:
            rr = attempt()
            break
        except TypeError as e:
            last = e
    else:
        raise last

    if not rr or (hasattr(rr, "isError") and rr.isError()):
        return False

    return True


def _setup_result(name, register, address, expected, action, reason, actual=None):

    return {
        "name": name,
        "register": register,
        "address": address,
        "expected": expected,
        "actual": actual,
        "action": action,
        "reason": reason,
    }


def _item(name, register, expected, actual, result, reason):

    return {
        "name": name,
        "register": register,
        "expected": expected,
        "actual": actual,
        "result": result,
        "reason": reason,
    }


def _actual_expected(items, name):

    for item in items:
        if item["name"] == name:
            return f"{item['actual']}/{item['expected']}"

    return "-"
