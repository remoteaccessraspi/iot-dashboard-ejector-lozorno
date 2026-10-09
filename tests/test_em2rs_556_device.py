import time
import unittest

from iot_core.core.config import load_config
from iot_core.devices.em2rs_556 import (
    Em2rs556Device,
    homing_delta,
    judge_word,
    motion_limit_s,
    overall_status,
    percent_to_steps,
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
