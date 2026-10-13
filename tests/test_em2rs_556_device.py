import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from iot_core.core.config import load_config
from iot_core.devices.em2rs_556 import (
    Em2rs556Device,
    clamp_position,
    half_trim_step,
    homing_delta,
    judge_word,
    motion_limit_s,
    overall_status,
    percent_to_steps,
    needs_boot_setup,
    park_target_steps,
    settle_remaining_s,
    settle_wait_s,
    trim_open_limit,
    trim_step_pulses,
    words_to_int32,
)


class _Response:

    def __init__(self, registers):

        self.registers = registers

    def isError(self):

        return False


class _Client:

    def __init__(self, blocks):

        self.blocks = blocks
        self.writes = []

    def read_holding_registers(self, address, count, device_id):

        words = self.blocks.get(address)

        if words is None or len(words) < count:
            return None

        return _Response(words[:count])

    def write_register(self, *args, **kwargs):

        self.writes.append((args, kwargs))
        raise AssertionError("EM2RS device must not write")


class _Cursor:

    def __init__(self):

        self.calls = []

    def __enter__(self):

        return self

    def __exit__(self, exc_type, exc, tb):

        return False

    def execute(self, sql, params=None):

        self.calls.append((sql, params))

    def fetchone(self):

        return None


class _Conn:

    def __init__(self):

        self.cursor_obj = _Cursor()

    def cursor(self):

        return self.cursor_obj


def _device():

    cfg = load_config()["em2rs_556"]
    return Em2rs556Device(slave_id=cfg["slave_id"], device_cfg=cfg)


class Em2rs556DeviceTest(unittest.TestCase):

    def test_absolute_position_word_fits_in_the_low_register(self):

        self.assertEqual(words_to_int32(0, 0), 0)
        self.assertEqual(words_to_int32(0, 600), 600)
        self.assertEqual(words_to_int32(0xFFFF, 0xFFFF), -1)

    def test_null_expected_is_not_a_match(self):

        result, _reason = judge_word(None, 1, None)
        self.assertEqual(result, "MANUAL_APPROVAL_REQUIRED")

    def test_planned_words_match_including_absolute_mode_and_pause(self):

        device = _device()
        snapshot = {
            "pulse_per_revolution": 200,
            "peak_current": 8,
            "path0_mode": 1,
            "speed": 50,
            "acceleration": 100,
            "deceleration": 100,
            "pause_time": 0,
        }
        items = device._check_items(snapshot)

        self.assertEqual(overall_status(items), "CONFIG_MATCH")
        by_name = {item["name"]: item["result"] for item in items}
        self.assertEqual(by_name["path0_mode"], "MATCH")
        self.assertEqual(by_name["path0_pause_time"], "MATCH")

    def test_pr0_mismatch_blocks_a_match(self):

        device = _device()
        snapshot = {
            "pulse_per_revolution": 600,
            "peak_current": 8,
            "path0_mode": 1,
            "speed": 50,
            "acceleration": 100,
            "deceleration": 100,
            "pause_time": 0,
        }

        self.assertEqual(overall_status(device._check_items(snapshot)), "CONFIG_MISMATCH")

    def test_execute_reads_path0_block_and_does_not_write(self):

        device = _device()
        client = _Client({
            0x0001: [200],
            0x0191: [8],
            0x6200: [1, 0, 600, 50, 100, 100, 0],
        })
        conn = _Conn()

        device.execute(client, conn, "2026-10-09 14:20:00")

        self.assertEqual(client.writes, [])
        state_calls = [call for call in conn.cursor_obj.calls if "INSERT INTO em2rs_556_state" in call[0]]
        sql, params = state_calls[-1]
        self.assertIn("INSERT INTO em2rs_556_state", sql)
        self.assertEqual(params[2], "CONFIG_MATCH")
        self.assertEqual(params[7], 600)
        self.assertEqual(params[3], 200)
        self.assertEqual(params[4], 8)
        self.assertAlmostEqual(params[5], 0.8)

    def test_setup_writes_only_words_that_differ(self):

        device = _device()
        client = _Memory()
        client.blocks[0x0001] = [600]
        client.blocks[0x0191] = [8]
        client.blocks[0x6200] = [0x0041, 0, 600, 20, 100, 100, 5]

        results = device.apply_setup(client, frame_delay_s=0)

        written = {item["address"]: item["expected"] for item in results if item["action"] == "WROTE"}
        self.assertEqual(written, {0x0001: 200, 0x6200: 1, 0x6203: 50, 0x6206: 0})
        self.assertNotIn(0x6002, client.writes)
        self.assertNotIn(0x6201, client.writes)
        self.assertNotIn(0x6202, client.writes)
        self.assertEqual(client.blocks[0x0001], [200])
        self.assertEqual(client.blocks[0x6200][0], 1)
        self.assertEqual(client.blocks[0x6200][6], 0)
        self.assertEqual(client.blocks[0x6200][2], 600)

    def test_setup_skips_a_matching_drive(self):

        device = _device()
        client = _Memory()
        client.blocks[0x0001] = [200]
        client.blocks[0x0191] = [8]
        client.blocks[0x6200] = [1, 0, 600, 50, 100, 100, 0]

        results = device.apply_setup(client, frame_delay_s=0)

        self.assertEqual(client.writes, [])
        self.assertTrue(all(item["action"] == "SKIP" for item in results))

    def test_setup_refuses_the_command_register(self):

        device = Em2rs556Device(
            slave_id=31,
            device_cfg={
                "modbus": {"registers": {"command": {"address": 0x6002}}},
                "startup_check": {
                    "parameters": {
                        "command": {
                            "register": "command",
                            "policy": "check_only",
                            "expected": 16,
                        }
                    }
                },
            },
        )
        client = _Memory()

        results = device.apply_setup(client, frame_delay_s=0)

        self.assertEqual(results[0]["action"], "SKIP")
        self.assertEqual(client.writes, [])

    def test_motion_limit_uses_homing_steps_from_settings(self):

        cfg = load_config()["em2rs_556"]
        limit = motion_limit_s(cfg["valve"], cfg["motion"])

        self.assertEqual(cfg["valve"]["homing_steps"], 650)
        self.assertAlmostEqual(limit, 3.9)
        self.assertEqual(homing_delta(cfg["valve"]), -650)
        self.assertEqual(percent_to_steps(50, cfg["valve"]["full_travel_steps"]), 300)

    def test_timeout_sends_only_quick_stop(self):

        device = _armed()
        client = _Memory()
        device.motion_phase = "HOMING_MOVE"
        device._move_started = time.monotonic() - 10

        device._poll_motion(client, _Conn(), True, 0)

        self.assertEqual(client.writes, [0x6002])
        self.assertEqual(client.blocks[0x6002], [0x0040])
        self.assertTrue(device.alarm)
        self.assertEqual(device.motion_phase, "ALARM")

    def test_running_blocks_the_next_command(self):

        device = _armed()
        client = _Memory()
        conn = _ControlConn({"em2rs_homing": ("1", "click")})

        device._poll_motion(client, conn, True, 100)

        self.assertEqual(client.writes, [])
        self.assertEqual(device.motion_phase, "IDLE")

    def test_boot_setup_needs_a_changed_boot_in_either_mode(self):

        self.assertFalse(needs_boot_setup(None, "new"))
        self.assertFalse(needs_boot_setup("same", "same"))
        self.assertTrue(needs_boot_setup("old", "new"))
        self.assertEqual(park_target_steps({"park_percent": 50, "full_travel_steps": 600}), 300)

    def test_auto_reboot_starts_homing_and_remembers_the_boot(self):

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "em2rs_boot_id"
            device = _fresh()
            device.note_boot("old-boot", "new-boot", path)
            client = _drive()
            conn = _StateConn(("AUTO", 1, "starý alarm", "POSITION_MOVE", 1, 37.0, 222))

            device._poll_motion(client, conn, False, 100)

            self.assertEqual(device.motion_phase, "HOMING_MOVE")
            self.assertFalse(device.position_valid)
            self.assertFalse(device.alarm)
            self.assertEqual(device.hmi_mode, "AUTO")
            self.assertEqual(client.blocks[0x6200][0], 0x0041)
            self.assertEqual(client.blocks[0x6200][1], 0xFFFF)
            self.assertEqual(client.blocks[0x6200][2], 0xFD76)
            self.assertEqual(client.blocks[0x6002], [0x0010])
            self.assertEqual(path.read_text(encoding="utf-8").strip(), "new-boot")

    def test_same_boot_keeps_auto_still(self):

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "em2rs_boot_id"
            device = _fresh()
            device.note_boot("same-boot", "same-boot", path)
            client = _drive()
            conn = _StateConn(("AUTO", 0, None, "IDLE", 1, 37.0, 222))

            device._poll_motion(client, conn, False, 210)

            self.assertEqual(device.motion_phase, "IDLE")
            self.assertTrue(device.position_valid)
            self.assertEqual(client.writes, [])
            self.assertEqual(path.read_text(encoding="utf-8").strip(), "same-boot")

    def test_manual_reboot_starts_homing_and_then_parks(self):

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "em2rs_boot_id"
            device = _fresh()
            device.note_boot("old-boot", "new-boot", path)
            client = _drive()
            conn = _StateConn(("MANUAL", 0, None, "IDLE", 1, 37.0, 222))

            device._poll_motion(client, conn, False, 210)

            self.assertEqual(device.motion_phase, "HOMING_MOVE")
            self.assertFalse(device.position_valid)
            self.assertTrue(device._park_after_homing)
            self.assertEqual(device.hmi_mode, "MANUAL")
            self.assertEqual(path.read_text(encoding="utf-8").strip(), "new-boot")

        device = _armed()
        device.position_valid = True
        device._park_after_homing = True
        device.gd20_running = True
        client = _drive()

        device._poll_motion(client, _Conn(), False, 0)

        self.assertEqual(device.motion_phase, "POSITION_MOVE")
        self.assertEqual(device.requested_position_steps, 300)
        self.assertFalse(device._park_after_homing)
        self.assertEqual(client.blocks[0x6200][2], 300)

    def test_stop_parks_the_valve_and_ignores_manual_moves(self):

        device = _armed()
        device.position_valid = True
        device.gd20_running = False
        device.hmi_mode = "MANUAL"
        client = _drive()
        conn = _ControlConn({"em2rs_position_pct": ("10", "click"), "em2rs_homing": ("1", "click")})

        device._poll_motion(client, conn, False, 210)

        self.assertEqual(device.motion_phase, "POSITION_MOVE")
        self.assertEqual(device.requested_position_steps, 300)
        self.assertEqual(client.blocks[0x6200][2], 300)

        client.writes.clear()
        device.motion_phase = "IDLE"
        device._poll_motion(client, conn, False, 300)

        self.assertEqual(client.writes, [0x000F])
        self.assertEqual(client.blocks[0x000F], [0])
        self.assertEqual(device.motion_phase, "IDLE")
        self.assertEqual(device._seen["em2rs_position_pct"], "click")
        self.assertEqual(device._seen["em2rs_homing"], "click")

    def test_stop_drops_trim_before_parking(self):

        device, conn, now, client = _trimmer(158.4)
        device.gd20_running = False
        device._trim_step = 40
        device.motion_phase = "TRIM_SETTLE"

        device._poll_motion(client, conn, False, 100, now)

        self.assertIsNone(device._trim_step)
        self.assertEqual(device.motion_phase, "POSITION_MOVE")
        self.assertEqual(device.requested_position_steps, 300)

    def test_running_inverter_does_not_park(self):

        device = _armed()
        device.position_valid = True
        device.gd20_running = True
        client = _drive()

        device._poll_motion(client, _Conn(), False, 210)

        self.assertEqual(client.writes, [])
        self.assertEqual(device.motion_phase, "IDLE")

    def test_auto_reboot_waits_until_the_counter_is_readable(self):

        device = _fresh()
        device.note_boot("old-boot", "new-boot")
        client = _drive()
        conn = _StateConn(("AUTO", 0, None, "IDLE", 1, 0, 0))

        device._poll_motion(client, conn, False, None)

        self.assertEqual(device.motion_phase, "IDLE")
        self.assertFalse(device.position_valid)
        self.assertEqual(client.writes, [])
        self.assertTrue(device._boot_homing)

        device._poll_motion(client, conn, False, 40)

        self.assertEqual(device.motion_phase, "HOMING_MOVE")
        self.assertFalse(device._boot_homing)

    def test_trim_step_and_wait_follow_the_approved_rules(self):

        self.assertEqual(trim_step_pulses(18, 0.18), 100)
        self.assertEqual(clamp_position(500, 980, 0, 600), 600)
        self.assertEqual(half_trim_step(100), 50)
        self.assertEqual(half_trim_step(1), 0)
        table = [
            {"max_steps": 15, "wait_s": 30},
            {"max_steps": 35, "wait_s": 70},
            {"max_steps": 130, "wait_s": 130},
        ]
        self.assertEqual(settle_wait_s(33, table, 5), 70)
        self.assertAlmostEqual(settle_wait_s(357, table, 5), 243.5)
        self.assertIsNone(settle_remaining_s(None, 10))
        self.assertEqual(settle_remaining_s(10, 12), 0.0)
        self.assertAlmostEqual(settle_remaining_s(70, 10), 60)

    def test_trim_settle_publishes_remaining_wait(self):

        device = _fresh()
        device._trim_step = 20
        started = time.time()
        device._begin_trim_settle()

        self.assertEqual(device.motion_phase, "TRIM_SETTLE")
        self.assertEqual(device._trim_settle_wait, 70)
        self.assertAlmostEqual(device._trim_settle_deadline - started, 70, delta=1)
        self.assertAlmostEqual(
            settle_remaining_s(device._trim_settle_deadline, started),
            70,
            delta=1,
        )

        device, conn, now, client = _trimmer(100.0)
        device._trim_step = 40
        device._trim_settle_mono = time.monotonic()
        device._trim_settle_wait = 100
        device._trim_settle_deadline = 1_000_000.0
        device._trim_extended = False
        device.motion_phase = "TRIM_SETTLE"

        for value in (100.0, 101.5, 102.0):
            conn.cursor_obj.p7 = value
            device._poll_motion(client, conn, False, 100, now)

        self.assertFalse(device._trim_extended)
        device._trim_settle_mono = time.monotonic() - 200
        conn.cursor_obj.p7 = 103.0
        device._poll_motion(client, conn, False, 100, now)

        self.assertTrue(device._trim_extended)
        self.assertEqual(device.motion_phase, "TRIM_SETTLE")
        self.assertAlmostEqual(device._trim_settle_deadline, 1_000_060.0)
        device._clear_trim()
        self.assertIsNone(device._trim_settle_deadline)

    def test_trim_starts_after_three_samples(self):

        device, conn, now, client = _trimmer(158.4)

        device._poll_motion(client, conn, False, 0, now)
        device._poll_motion(client, conn, False, 0, now)
        self.assertEqual(client.writes, [])

        device._poll_motion(client, conn, False, 0, now)

        self.assertEqual(device.motion_phase, "POSITION_MOVE")
        self.assertEqual(device.requested_position_steps, 100)
        self.assertEqual(client.blocks[0x6200][0], 0x0001)
        self.assertEqual(client.blocks[0x6200][2], 100)

    def test_trim_waits_then_halves_without_a_p7_response(self):

        device, conn, now, client = _trimmer(158.4)
        device._trim_step = 100
        device._trim_p7_before = 158.4
        device._trim_extended = True
        device._trim_settle_mono = time.monotonic() - 5
        device._trim_settle_wait = 0
        device.motion_phase = "TRIM_SETTLE"

        device._poll_motion(client, conn, False, 100, now)

        self.assertEqual(device.motion_phase, "POSITION_MOVE")
        self.assertEqual(device.requested_position_steps, 150)
        self.assertEqual(device._trim_step, 50)

    def test_trim_stops_inside_the_stop_band(self):

        device, conn, now, client = _trimmer(175.5)
        device._trim_step = 100
        device._trim_p7_before = 170.0
        device._trim_extended = True
        device._trim_settle_mono = time.monotonic() - 5
        device._trim_settle_wait = 0
        device.motion_phase = "TRIM_SETTLE"

        device._poll_motion(client, conn, False, 100, now)

        self.assertEqual(device.motion_phase, "IDLE")
        self.assertEqual(client.writes, [])
        self.assertIsNone(device._trim_step)

    def test_trim_holds_the_next_step_until_invt_is_stable(self):

        device, conn, now, client = _trimmer(158.4)
        device.gd20_stable = False
        device._trim_step = 100
        device._trim_extended = True
        device._trim_settle_mono = time.monotonic() - 5
        device._trim_settle_wait = 0
        device.motion_phase = "TRIM_SETTLE"

        device._poll_motion(client, conn, False, 100, now)

        self.assertEqual(device.motion_phase, "TRIM_HOLD")
        self.assertEqual(client.writes, [])

        device.gd20_stable = True
        device._trim_p7_before = 158.4
        device._poll_motion(client, conn, False, 100, now)

        self.assertEqual(device.requested_position_steps, 150)

    def test_trim_closes_when_p7_is_above_the_setpoint(self):

        device, conn, now, client = _trimmer(183.6)
        device._trim_step = 172
        device._trim_p7_before = 114.2
        device._trim_extended = True
        device._trim_settle_mono = time.monotonic() - 5
        device._trim_settle_wait = 0
        device.motion_phase = "TRIM_SETTLE"

        device._poll_motion(client, conn, False, 517, now)

        self.assertEqual(device.requested_position_steps, 300)
        self.assertEqual(device._trim_step, -217)

    def test_trim_stops_at_half_travel(self):

        trim = _fresh().device_cfg["valve"]["p7_trim"]
        k = float(trim["k_kpa_per_step"])
        self.assertAlmostEqual(trim["stop_band_kpa"], 6 * k)
        self.assertAlmostEqual(trim["sensitivity_kpa"], 11 * k)
        self.assertEqual(trim_open_limit(600, 50, 600), 300)
        device, conn, now, client = _trimmer(100.0)

        device._poll_motion(client, conn, False, 250, now)
        device._poll_motion(client, conn, False, 250, now)
        device._poll_motion(client, conn, False, 250, now)

        self.assertEqual(device.requested_position_steps, 300)
        self.assertLessEqual(device.requested_position_steps, 300)

    def test_gd20_within_band_is_stable(self):

        device = _fresh()
        now = datetime(2026, 10, 12, 13, 55, 0)
        device.note_gd20(100, 3, 10)
        device._apply_gd20((1, 1, 811.5, 810.0, now), now)

        self.assertTrue(device.gd20_stable)
        self.assertAlmostEqual(device.gd20_error_kpa, -1.5)

    def test_auto_does_not_move(self):

        device = _armed()
        device.hmi_mode = "AUTO"
        client = _Memory()
        conn = _ControlConn({"em2rs_homing": ("1", "click"), "em2rs_position_pct": ("50", "click")})

        device._poll_motion(client, conn, False, 0)

        self.assertEqual(client.writes, [])

    def test_homing_zeroes_only_after_the_expected_delta(self):

        device = _armed()
        client = _drive()
        conn = _ControlConn({"em2rs_homing": ("1", "click")})

        device._poll_motion(client, conn, False, 100)

        self.assertEqual(client.blocks[0x6200][0], 0x0041)
        self.assertEqual(client.blocks[0x6200][1], 0xFFFF)
        self.assertEqual(client.blocks[0x6200][2], 0xFD76)
        self.assertEqual(client.blocks[0x6002], [0x0010])
        self.assertEqual(device.motion_phase, "HOMING_MOVE")

        client.writes.clear()
        device._poll_motion(client, conn, False, 100)

        self.assertEqual(client.writes, [0x000F])
        self.assertEqual(client.blocks[0x000F], [0])
        self.assertTrue(device.alarm)
        self.assertNotEqual(device.motion_phase, "HOMING_ZERO")

        device = _armed()
        client = _drive()
        device._poll_motion(client, conn, False, 100)
        client.writes.clear()
        device._poll_motion(client, conn, False, 100 - 650)

        self.assertEqual(client.writes, [0x6002])
        self.assertEqual(client.blocks[0x6002], [0x0021])
        self.assertEqual(device.motion_phase, "HOMING_ZERO")

        client.writes.clear()
        device._poll_motion(client, conn, False, 0)

        self.assertTrue(device.position_valid)
        self.assertEqual(device.motion_phase, "IDLE")
        self.assertEqual(client.blocks[0x6200][0], 0x0001)
        self.assertEqual(client.blocks[0x000F], [0])
        self.assertNotIn(0x0010, client.blocks[0x6002])

    def test_position_checks_the_counter_delta(self):

        device = _armed()
        device.position_valid = True
        client = _drive()
        conn = _ControlConn({"em2rs_position_pct": ("50", "click")})

        device._poll_motion(client, conn, False, 0)

        self.assertEqual(client.blocks[0x6200][0], 0x0001)
        self.assertEqual(client.blocks[0x6200][2], 300)
        self.assertEqual(client.blocks[0x000F], [1])
        self.assertEqual(device.requested_position_steps, 300)

        client.writes.clear()
        device._poll_motion(client, conn, False, 200)

        self.assertEqual(device.position_check, "DIFFERENT")
        self.assertEqual(device.expected_delta_steps, 300)
        self.assertEqual(device.actual_delta_steps, 200)
        self.assertTrue(device.alarm)
        self.assertEqual(client.writes, [0x000F])
        self.assertEqual(client.blocks[0x000F], [0])


class _TrimCursor(_Cursor):

    def __init__(self, now, p7, setpoint):

        super().__init__()
        self.now = now
        self.p7 = p7
        self.setpoint = setpoint
        self._one = None

    def execute(self, sql, params=None):

        super().execute(sql, params)
        self._one = None

        if "conversion_table" in sql:
            self._one = (self.now, self.p7)
        elif params and "control_state" in sql and params[0] == "em2rs_p7_setpoint_kpa":
            self._one = (self.setpoint, self.now)

    def fetchone(self):

        return self._one


class _TrimConn:

    def __init__(self, now, p7, setpoint):

        self.cursor_obj = _TrimCursor(now, p7, setpoint)

    def cursor(self):

        return self.cursor_obj


def _trimmer(p7, setpoint="176.4"):

    device = _fresh()
    device.hmi_mode = "AUTO"
    device.position_valid = True
    device.gd20_stable = True
    device._state_loaded = True
    device._requests_seeded = True
    device._seen = {
        "em2rs_mode": "seed",
        "em2rs_homing": "seed",
        "em2rs_position_pct": "seed",
        "em2rs_alarm_reset": "seed",
    }
    device.device_cfg["valve"]["p7_trim"]["enabled"] = True
    now = datetime(2026, 10, 12, 14, 5, 0)
    return device, _TrimConn(now, p7, setpoint), now, _drive()


def _fresh():

    device = _device()
    device.frame_delay_s = 0
    device.device_cfg["safety"]["motion_writes_enabled"] = True
    return device


def _armed():

    device = _device()
    device.frame_delay_s = 0
    device._state_loaded = True
    device._requests_seeded = True
    device.device_cfg["safety"]["motion_writes_enabled"] = True
    device._seen = {
        "em2rs_mode": None,
        "em2rs_homing": "seed",
        "em2rs_position_pct": "seed",
        "em2rs_alarm_reset": "seed",
    }
    return device


def _drive():

    client = _Memory()
    client.blocks[0x6200] = [1, 0, 0, 50, 100, 100, 0]
    client.blocks[0x6002] = [0]
    client.blocks[0x1003] = [0]
    client.blocks[0x602C] = [0, 0]
    return client


class _StateCursor(_Cursor):

    def __init__(self, state_row):

        super().__init__()
        self.state_row = state_row
        self._one = None

    def execute(self, sql, params=None):

        super().execute(sql, params)
        self._one = self.state_row if "FROM em2rs_556_state" in sql else None

    def fetchone(self):

        return self._one


class _StateConn:

    def __init__(self, state_row):

        self.cursor_obj = _StateCursor(state_row)

    def cursor(self):

        return self.cursor_obj


class _ControlCursor(_Cursor):

    def __init__(self, rows):

        super().__init__()
        self.rows = rows
        self._one = None

    def execute(self, sql, params=None):

        super().execute(sql, params)
        self._one = None
        if params and "control_state" in sql:
            self._one = self.rows.get(params[0])

    def fetchone(self):

        return self._one


class _ControlConn:

    def __init__(self, rows):

        self.cursor_obj = _ControlCursor(rows)

    def cursor(self):

        return self.cursor_obj


class _Memory:

    def __init__(self):

        self.blocks = {}
        self.writes = []

    def read_holding_registers(self, address, count, device_id):

        for base, words in self.blocks.items():
            if base <= address < base + len(words) and address + count <= base + len(words):
                offset = address - base
                return _Response(words[offset:offset + count])

        return None

    def write_register(self, address, value, device_id):

        self.writes.append(address)

        for base, words in self.blocks.items():
            if base <= address < base + len(words):
                words[address - base] = value
                return _Response([])

        self.blocks[address] = [value]
        return _Response([])


if __name__ == "__main__":
    unittest.main()
