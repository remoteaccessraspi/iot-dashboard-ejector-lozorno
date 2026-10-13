import time
from datetime import datetime
from pathlib import Path

from iot_core.devices.base_device import BaseDevice
from iot_core.devices.invt_gd20 import gd20_is_running, gd20_sample_age_s, gd20_stability
from iot_core.modbus.compat import call_with_fallback

_BOOT_ID_PATH = Path(__file__).resolve().parents[2] / "var" / "em2rs_boot_id"
_BOOT_ID_FILE = Path("/proc/sys/kernel/random/boot_id")


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


def trim_step_pulses(error_kpa, k_kpa_per_step):

    k = float(k_kpa_per_step)

    if k == 0:
        return 0

    return int(round(float(error_kpa) / k))


def trim_open_limit(full_travel_steps, max_open_percent, valve_max):

    high = int(valve_max)

    if max_open_percent is None:
        return high

    return min(high, percent_to_steps(max_open_percent, full_travel_steps))


def clamp_position(actual, step, low, high):

    target = int(actual) + int(step)

    if target < int(low):
        return int(low)

    if target > int(high):
        return int(high)

    return target


def half_trim_step(step):

    sign = 1 if int(step) > 0 else -1
    halved = int(round(abs(int(step)) / 2.0))

    return sign * halved


def settle_wait_s(steps, table, extra_per_10):

    steps = abs(int(steps))
    last = None

    for row in table or []:
        last = row

        if steps <= int(row["max_steps"]):
            return float(row["wait_s"])

    if last is None:
        return 0.0

    wait = float(last["wait_s"])
    over = steps - int(last["max_steps"])

    if over > 0 and extra_per_10:
        wait += (over / 10.0) * float(extra_per_10)

    return wait


def settle_remaining_s(deadline, now_epoch):

    if deadline is None or now_epoch is None:
        return None

    try:
        remaining = float(deadline) - float(now_epoch)
    except (TypeError, ValueError):
        return None

    if remaining < 0:
        return 0.0

    return remaining


def needs_boot_setup(stored_boot_id, current_boot_id):

    if not stored_boot_id or not current_boot_id:
        return False

    return str(stored_boot_id) != str(current_boot_id)


def park_target_steps(valve):

    if not valve or valve.get("park_percent") is None:
        return None

    full = valve.get("full_travel_steps")

    if not full:
        return None

    return percent_to_steps(valve["park_percent"], full)


def current_boot_id():

    try:
        text = _BOOT_ID_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    return text or None


def stored_boot_id(path):

    try:
        text = Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None

    return text or None


def save_boot_id(path, boot_id):

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(str(boot_id).strip() + "\n", encoding="utf-8")
    temporary.replace(path)


def attach_boot(device, path=None, current=None, stored=None):

    path = _BOOT_ID_PATH if path is None else Path(path)

    if current is None:
        current = current_boot_id()

    if stored is None:
        stored = stored_boot_id(path)

    device.note_boot(stored, current, path)


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
        self._stored_boot_id = None
        self._current_boot_id = None
        self._boot_path = None
        self._boot_homing = False
        self._boot_applied = False
        self._boot_committed = False
        self._gd20_slave_id = None
        self._gd20_tolerance_kpa = None
        self._gd20_max_age_s = None
        self.gd20_stable = False
        self.gd20_error_kpa = None
        self.gd20_running = None
        self._park_after_homing = False
        self._trim_step = None
        self._trim_p7_before = None
        self._trim_confirm = 0
        self._trim_settle_mono = None
        self._trim_settle_wait = None
        self._trim_settle_deadline = None
        self._trim_settle_p7 = []
        self._trim_extended = False

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
        self._read_gd20(db_conn, ts)
        gd20_text = "ustálený" if self.gd20_stable else "nie"
        gd20_error = "-" if self.gd20_error_kpa is None else f"{self.gd20_error_kpa:.1f}"

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
            f"gd20={gd20_text}/{gd20_error}",
        )

        try:
            running = self._read_running(client)
            actual_steps = self._read_actual_steps(client)
            self._poll_motion(client, db_conn, running, actual_steps, ts)
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

    def _poll_motion(self, client, db_conn, running, actual_steps, now=None):

        if now is None:
            now = datetime.now()

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

        if self._poll_boot_homing(client, actual_steps):
            return

        if self._park_after_homing and self.motion_phase == "IDLE" and self.position_valid and not self.alarm:
            self._park_after_homing = False
            if self._start_park(client, actual_steps):
                return

        if self._hold_park(client, actual_steps):
            return

        self._accept_requests(client, db_conn, actual_steps)
        self._poll_trim(client, db_conn, actual_steps, now)

        if self.motion_phase == "IDLE":
            self._set_enable(client, False)

    def _trip_timeout(self, client, limit, steps):

        self._quick_stop(client)
        self._clear_trim()
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
            self._set_enable(client, False)
            if self._trim_step is not None:
                self._begin_trim_settle()
                print(f"EM2RS trim pozícia {self._target_steps} ok")
                return
            self.motion_phase = "IDLE"
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

        if self.gd20_running is False and self.position_valid:
            for name in ("em2rs_homing", "em2rs_position_pct"):
                row = rows[name]
                if row is not None:
                    self._seen[name] = row[1]
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
            self._arm_boot_homing(self.hmi_mode)
            return

        mode, alarm, text, phase, valid, pct, steps = row[:7]

        if mode in ("MANUAL", "AUTO"):
            self.hmi_mode = mode

        self.position_valid = bool(valid)
        self.requested_position_pct = pct
        self.requested_position_steps = steps

        if self._arm_boot_homing(mode):
            return

        if alarm:
            self.alarm = True
            self.alarm_text = text
            self.motion_phase = "ALARM"
            return

        if phase in ("HOMING_MOVE", "HOMING_ZERO", "POSITION_MOVE"):
            self.alarm = True
            self.alarm_text = "pohyb prerušený reštartom"
            self.motion_phase = "ALARM"

    def note_gd20(self, slave_id, tolerance_kpa, max_age_s):

        self._gd20_slave_id = None if slave_id is None else int(slave_id)
        self._gd20_tolerance_kpa = None if tolerance_kpa is None else float(tolerance_kpa)
        self._gd20_max_age_s = None if max_age_s is None else float(max_age_s)

    def _read_gd20(self, db_conn, now):

        if self._gd20_slave_id is None:
            self._apply_gd20(None, now)
            return

        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT online, running, pid_setpoint_kpa, pid_feedback_kpa, updated_ts,
                           status_code
                    FROM invt_gd20_state
                    WHERE device_id = %s
                    """,
                    (self._gd20_slave_id,),
                )
                row = cur.fetchone()
        except Exception as e:
            print("EM2RS GD20 read:", e)
            self._apply_gd20(None, now)
            return

        self._apply_gd20(row, now)

    def _apply_gd20(self, row, now):

        if not row:
            self.gd20_stable = False
            self.gd20_error_kpa = None
            self.gd20_running = None
            return

        online, running, setpoint, feedback, updated = row[:5]
        status = row[5] if len(row) > 5 else None
        age = gd20_sample_age_s(updated, now)
        tolerance = self._trim_cfg().get("invt_tolerance_kpa", self._gd20_tolerance_kpa)
        self.gd20_running = self._known_gd20_running(online, status, age)
        stable, error = gd20_stability(
            setpoint,
            feedback,
            tolerance,
            running,
            online,
            age,
            self._gd20_max_age_s,
        )
        self.gd20_stable = stable
        self.gd20_error_kpa = error

    def note_boot(self, stored_boot_id, current_boot_id, path=None):

        self._stored_boot_id = None if stored_boot_id is None else str(stored_boot_id).strip()
        self._current_boot_id = None if current_boot_id is None else str(current_boot_id).strip()
        self._boot_path = None if path is None else Path(path)

    def _arm_boot_homing(self, mode):

        if self._boot_applied:
            return False

        self._boot_applied = True

        if not needs_boot_setup(self._stored_boot_id, self._current_boot_id):
            self._commit_boot_id()
            return False

        self._boot_homing = True
        self._park_after_homing = True
        self.position_valid = False
        self.alarm = False
        self.alarm_text = None
        self.motion_phase = "IDLE"
        print("EM2RS reboot, homing čaká na počítadlo")
        return True

    def _poll_boot_homing(self, client, actual_steps):

        if not self._boot_homing or self.motion_phase != "IDLE":
            return False

        if actual_steps is None:
            return False

        self._start_homing(client, actual_steps)

        if self.motion_phase != "HOMING_MOVE":
            return False

        self._boot_homing = False
        self._commit_boot_id()
        print("EM2RS homing po reboote")
        return True

    def _commit_boot_id(self):

        if self._boot_committed:
            return

        self._boot_committed = True

        if not self._boot_path or not self._current_boot_id:
            return

        save_boot_id(self._boot_path, self._current_boot_id)

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

    def _known_gd20_running(self, online, status_code, age):

        max_age = self._gd20_max_age_s
        fresh = (
            online
            and age is not None
            and max_age is not None
            and float(age) <= float(max_age)
        )

        if not fresh:
            return None

        return gd20_is_running(status_code)

    def _start_park(self, client, actual_steps):

        valve = self.device_cfg.get("valve") or {}
        target = park_target_steps(valve)

        if target is None or actual_steps is None:
            return False

        if int(actual_steps) == target:
            return False

        self._clear_trim()
        self._start_position(client, actual_steps, valve["park_percent"])
        return self.motion_phase == "POSITION_MOVE"

    def _hold_park(self, client, actual_steps):

        if self.gd20_running is not False or self.alarm:
            return False

        if self.motion_phase in ("TRIM_SETTLE", "TRIM_HOLD"):
            self._drop_trim_run()

        if self.motion_phase != "IDLE" or not self.position_valid:
            return False

        if self._start_park(client, actual_steps):
            print(f"EM2RS INVT stop, parkovanie {self.device_cfg['valve']['park_percent']:g} %")
            return True

        return False

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
        self._write_absolute_move(client, actual_steps, target, percent)
        print(f"EM2RS position start {percent:g}% -> {target}")

    def _write_absolute_move(self, client, actual_steps, target, percent):

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

    def _trim_cfg(self):

        return ((self.device_cfg.get("valve") or {}).get("p7_trim") or {})

    def _clear_trim(self):

        self._trim_step = None
        self._trim_p7_before = None
        self._trim_confirm = 0
        self._trim_settle_mono = None
        self._trim_settle_wait = None
        self._trim_settle_deadline = None
        self._trim_settle_p7 = []
        self._trim_extended = False

    def _drop_trim_run(self):

        self._clear_trim()

        if self.motion_phase in ("TRIM_SETTLE", "TRIM_HOLD"):
            self.motion_phase = "IDLE"

    def _poll_trim(self, client, db_conn, actual_steps, now):

        trim = self._trim_cfg()

        if not trim.get("enabled"):
            self._clear_trim()
            return

        if self.motion_phase == "POSITION_MOVE":
            return

        if self.hmi_mode != "AUTO" or not self.position_valid or self.alarm:
            self._drop_trim_run()
            return

        if self.motion_phase in ("TRIM_SETTLE", "TRIM_HOLD"):
            self._trim_after_wait(client, db_conn, actual_steps, now, trim)
            return

        if self.motion_phase != "IDLE" or actual_steps is None:
            return

        if not self.gd20_stable:
            self._trim_confirm = 0
            return

        setpoint, p7 = self._trim_sample(db_conn, now)

        if setpoint is None or p7 is None:
            self._trim_confirm = 0
            return

        error = setpoint - p7

        if abs(error) < float(trim["sensitivity_kpa"]):
            self._trim_confirm = 0
            return

        self._trim_confirm += 1

        if self._trim_confirm < int(trim["confirm_samples"]):
            print(f"EM2RS trim potvrdenie {self._trim_confirm}, chyba {error:.1f} kPa")
            return

        self._trim_confirm = 0
        step = trim_step_pulses(error, trim["k_kpa_per_step"])
        self._send_trim_step(client, actual_steps, step, p7)

    def _trim_sample(self, db_conn, now):

        row = self._control_row(db_conn, "em2rs_p7_setpoint_kpa")
        setpoint = None

        if row is not None and row[0] is not None:
            try:
                setpoint = float(str(row[0]).strip())
            except ValueError:
                setpoint = None

        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ts, p7
                    FROM conversion_table
                    ORDER BY id DESC
                    LIMIT 1
                    """
                )
                sample = cur.fetchone()
        except Exception as e:
            print("EM2RS p7 read:", e)
            return setpoint, None

        if not sample or sample[1] is None:
            return setpoint, None

        max_age = self._gd20_max_age_s if self._gd20_max_age_s is not None else 10.0
        age = gd20_sample_age_s(sample[0], now)

        if age is None or age > max_age:
            return setpoint, None

        return setpoint, float(sample[1])

    def _send_trim_step(self, client, actual_steps, step, p7):

        valve = self.device_cfg["valve"]
        trim = self._trim_cfg()
        open_limit = trim_open_limit(
            valve["full_travel_steps"],
            trim.get("max_open_percent"),
            valve["max_position_steps"],
        )
        target = clamp_position(
            actual_steps,
            step,
            valve["min_position_steps"],
            open_limit,
        )
        delta = target - int(actual_steps)

        if delta == 0:
            print("EM2RS trim krok 0, stojí na doraze")
            self._clear_trim()
            self.motion_phase = "IDLE"
            return

        if not self._motion_allowed() or self.running or actual_steps is None:
            return

        self._trim_step = delta
        self._trim_p7_before = p7
        full = int(valve["full_travel_steps"])
        percent = None if not full else target * 100.0 / full
        self._write_absolute_move(client, actual_steps, target, percent)
        print(f"EM2RS trim {delta} pulzov -> {target}, p7 {p7:.1f}")

    def _begin_trim_settle(self):

        trim = self._trim_cfg()
        self._trim_settle_mono = time.monotonic()
        self._trim_settle_wait = settle_wait_s(
            self._trim_step,
            trim.get("settle_wait"),
            trim.get("settle_extra_per_10_steps_s"),
        )
        self._trim_settle_deadline = time.time() + self._trim_settle_wait
        self._trim_settle_p7 = []
        self._trim_extended = False
        self.motion_phase = "TRIM_SETTLE"
        print(f"EM2RS trim čaká {self._trim_settle_wait:.0f} s")

    def _trim_after_wait(self, client, db_conn, actual_steps, now, trim):

        setpoint, p7 = self._trim_sample(db_conn, now)

        if p7 is not None:
            self._trim_settle_p7.append(p7)

        if self.motion_phase == "TRIM_SETTLE":
            elapsed = time.monotonic() - self._trim_settle_mono

            if elapsed < self._trim_settle_wait:
                return

            count = int(trim["settle_span_samples"])
            window = self._trim_settle_p7[-count:]

            if (
                not self._trim_extended
                and len(window) >= count
                and max(window) - min(window) >= float(trim["settle_span_kpa"])
            ):
                self._trim_extended = True
                extra = float(trim["settle_extra_s"])
                self._trim_settle_wait += extra
                if self._trim_settle_deadline is not None:
                    self._trim_settle_deadline += extra
                print("EM2RS trim čakanie predĺžené, p7 sa ešte hýbe")
                return

        if not self.gd20_stable:
            if self.motion_phase != "TRIM_HOLD":
                self.motion_phase = "TRIM_HOLD"
                print("EM2RS trim čaká na INVT")
            return

        if setpoint is None or p7 is None or actual_steps is None:
            return

        error = setpoint - p7

        if abs(error) <= float(trim["stop_band_kpa"]):
            print(f"EM2RS trim v pásme, chyba {error:.1f} kPa")
            self._clear_trim()
            self.motion_phase = "IDLE"
            return

        no_response = (
            self._trim_p7_before is not None
            and abs(p7 - self._trim_p7_before) < float(trim["no_response_kpa"])
        )

        if no_response:
            print(f"EM2RS trim p7 bez odozvy, chyba {error:.1f} kPa")
            step = half_trim_step(self._trim_step)
        else:
            step = trim_step_pulses(error, trim["k_kpa_per_step"])

        if step == 0:
            print("EM2RS trim polovica je 0")
            self._clear_trim()
            self.motion_phase = "IDLE"
            return

        self._send_trim_step(client, actual_steps, step, p7)

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

        self._clear_trim()
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
            "trim_settle_deadline",
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
            self._trim_settle_deadline if self.motion_phase == "TRIM_SETTLE" else None,
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
