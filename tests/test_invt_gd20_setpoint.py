import unittest
from datetime import datetime

from app import gd20_row_visible
from iot_core.core.config import load_config
from iot_core.devices.invt_gd20 import InvtGd20Device, gd20_is_running, gd20_stability, kpa_to_pid_raw


class Gd20StabilityTest(unittest.TestCase):

    def test_band_includes_the_boundary_and_rejects_the_next_step(self):

        stable, error = gd20_stability(811.5, 814.5, 3, 1, 1, 1, 10)
        self.assertTrue(stable)
        self.assertAlmostEqual(error, 3)

        stable, error = gd20_stability(811.5, 807.0, 3, 1, 1, 1, 10)
        self.assertFalse(stable)
        self.assertAlmostEqual(error, -4.5)

    def test_stopped_or_stale_sample_is_not_stable(self):

        self.assertFalse(gd20_stability(811.5, 811.5, 3, 0, 1, 1, 10)[0])
        self.assertFalse(gd20_stability(811.5, 811.5, 3, 1, 0, 1, 10)[0])
        self.assertFalse(gd20_stability(811.5, 811.5, 3, 1, 1, 11, 10)[0])
        self.assertFalse(gd20_stability(None, 811.5, 3, 1, 1, 1, 10)[0])

    def test_status_word_decides_running(self):

        self.assertTrue(gd20_is_running(1))
        self.assertTrue(gd20_is_running(2))
        self.assertFalse(gd20_is_running(3))
        self.assertFalse(gd20_is_running(4))
        self.assertFalse(gd20_is_running(5))
        self.assertIsNone(gd20_is_running(None))


class _Response:

    def isError(self):

        return False


class _Client:

    def __init__(self):

        self.writes = []

    def write_register(self, address, value, device_id):

        self.writes.append((address, value, device_id))
        return _Response()


class _Cursor:

    def __init__(self, row):

        self.row = row

    def __enter__(self):

        return self

    def __exit__(self, exc_type, exc, tb):

        return False

    def execute(self, sql, params=None):

        return None

    def fetchone(self):

        return self.row


class _Conn:

    def __init__(self, row):

        self.row = row

    def cursor(self):

        return _Cursor(self.row)


class Gd20SetpointSyncTest(unittest.TestCase):

    def setUp(self):

        cfg = load_config()["invt_gd20"]
        self.command = cfg["commands"]["pid_reference"]
        self.device = InvtGd20Device(slave_id=100, device_cfg=cfg)
        self.ts = datetime(2026, 10, 10, 10, 0, 0)

    def test_mismatch_is_written_on_the_first_cycle(self):

        client = _Client()
        written = self.device._apply_pending_setpoint(
            client,
            _Conn(("811", self.ts)),
            0,
        )

        raw = kpa_to_pid_raw(811, self.command)
        self.assertEqual(client.writes, [(0x2002, raw, 100)])
        self.assertEqual(written, 811.5)

    def test_quantized_readback_is_not_rewritten(self):

        client = _Client()
        written = self.device._apply_pending_setpoint(
            client,
            _Conn(("811", self.ts)),
            811.5,
        )

        self.assertEqual(client.writes, [])
        self.assertIsNone(written)

    def test_mismatch_is_retried_until_the_drive_matches(self):

        client = _Client()
        conn = _Conn(("811", self.ts))

        self.device._apply_pending_setpoint(client, conn, 0)
        self.device._apply_pending_setpoint(client, conn, 0)

        self.assertEqual(len(client.writes), 2)

    def test_missing_command_is_left_alone(self):

        client = _Client()
        written = self.device._apply_pending_setpoint(client, _Conn(None), 0)

        self.assertEqual(client.writes, [])
        self.assertIsNone(written)


class Gd20AliasVisibilityTest(unittest.TestCase):

    def test_na_alias_hides_the_card_row(self):

        cfg = {
            "invt_gd20": {
                "monitoring": {
                    "output_current": {"alias": "NA"},
                    "pid_setting": {
                        "alias": "pid_setpoint_percent",
                        "engineering_alias": "NA",
                    },
                },
                "commands": {
                    "pid_reference": {"alias": "pid_reference_command"},
                },
            }
        }

        visible = gd20_row_visible(cfg)

        self.assertFalse(visible["current"])
        self.assertFalse(visible["setpoint"])
        self.assertTrue(visible["setpoint_command"])
        self.assertTrue(visible["frequency"])


if __name__ == "__main__":
    unittest.main()
