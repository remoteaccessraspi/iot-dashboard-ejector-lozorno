import unittest
from datetime import datetime

from app import gd20_row_visible
from iot_core.core.config import load_config
from iot_core.devices.invt_gd20 import (
    InvtGd20Device,
    external_stop_active,
    gd20_is_running,
    gd20_setup_items,
    gd20_stability,
    kpa_to_pid_raw,
)


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

    def __init__(self, registers=None):

        self.registers = registers or []

    def isError(self):

        return False


class _SetupBus:

    def __init__(self, words):

        self.words = dict(words)
        self.writes = []
        self.reads = []

    def read_holding_registers(self, address, count, device_id):

        self.reads.append(address)

        if address not in self.words:
            return None

        return _Response([self.words[address]])

    def write_register(self, address, value, device_id):

        self.writes.append((address, value, device_id))
        self.words[address] = value
        return _Response()


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


class Gd20ExternalStopTest(unittest.TestCase):

    def setUp(self):

        cfg = load_config()["invt_gd20"]
        self.stop = cfg["external_stop"]
        self.device = InvtGd20Device(slave_id=100, device_cfg=cfg)
        self.device._command_seen = True
        self.device._command_ts = datetime(2026, 1, 1)

    def test_open_s4_is_active_after_polarity(self):

        self.assertTrue(external_stop_active(1 << 3, self.stop))
        self.assertFalse(external_stop_active(0, self.stop))
        self.assertIsNone(external_stop_active(None, self.stop))
        self.assertIsNone(external_stop_active(1 << 3, {"enabled": False, "bit": 3}))

    def test_run_during_external_stop_is_not_sent_after_the_switch_closes(self):

        client = _Client()
        ts = datetime(2026, 10, 14, 11, 0, 0)
        conn = _Conn(("1", ts))

        self.device._apply_pending_command(client, conn, external_stop=True)
        self.device._apply_pending_command(client, conn, external_stop=False)

        self.assertEqual(client.writes, [])

    def test_run_is_written_when_the_switch_is_closed(self):

        client = _Client()
        conn = _Conn(("1", datetime(2026, 10, 14, 11, 1, 0)))

        self.device._apply_pending_command(client, conn, external_stop=False)

        self.assertEqual(client.writes, [(0x2000, 0x0001, 100)])

    def test_stop_is_written_while_the_switch_is_open(self):

        client = _Client()
        conn = _Conn(("0", datetime(2026, 10, 14, 11, 2, 0)))

        self.device._apply_pending_command(client, conn, external_stop=True)

        self.assertEqual(client.writes, [(0x2000, 0x0005, 100)])


class Gd20SetupTest(unittest.TestCase):

    def setUp(self):

        self.cfg = load_config()["invt_gd20"]
        self.device = InvtGd20Device(slave_id=100, device_cfg=self.cfg)

    def test_settings_list_the_boot_parameters(self):

        items = gd20_setup_items(self.cfg)

        self.assertEqual(
            [(item["parameter"], item["expected"], item["stop_only"]) for item in items],
            [
                ("P01.21", 0, False),
                ("P05.10", 8, False),
                ("P00.01", 2, True),
                ("P05.04", 6, True),
            ],
        )

    def test_setup_writes_only_words_that_differ_and_polarity_before_s4(self):

        bus = _SetupBus({
            0x2100: 3,
            0x0115: 1,
            0x050A: 0,
            0x0001: 2,
            0x0504: 0,
            0x0006: 0,
        })

        results = self.device.apply_setup(bus, frame_delay_s=0)

        self.assertEqual(bus.writes, [(0x0115, 0, 100), (0x050A, 8, 100), (0x0504, 6, 100)])
        self.assertEqual(
            [item["action"] for item in results],
            ["WROTE", "WROTE", "SKIP", "WROTE"],
        )
        self.assertTrue(self.device._setup_done)
        self.assertNotIn(0x0006, [address for address, _value, _slave in bus.writes])

    def test_setup_skips_a_matching_drive(self):

        bus = _SetupBus({0x2100: 3, 0x0115: 0, 0x050A: 8, 0x0001: 2, 0x0504: 6})

        results = self.device.apply_setup(bus, frame_delay_s=0)

        self.assertEqual(bus.writes, [])
        self.assertTrue(all(item["action"] == "SKIP" for item in results))
        self.assertTrue(self.device._setup_done)
        reads = len(bus.reads)
        self.assertEqual(self.device.apply_setup(bus, frame_delay_s=0), [])
        self.assertEqual(len(bus.reads), reads)

    def test_stop_only_parameters_wait_until_the_drive_stops(self):

        bus = _SetupBus({0x2100: 1, 0x0115: 0, 0x050A: 0, 0x0001: 0, 0x0504: 0})

        running = self.device.apply_setup(bus, frame_delay_s=0, running=1)

        self.assertEqual(bus.writes, [(0x050A, 8, 100)])
        self.assertEqual([item["action"] for item in running], ["SKIP", "WROTE", "DEFER", "DEFER"])
        self.assertFalse(self.device._setup_done)

        bus.words[0x2100] = 3
        stopped = self.device.apply_setup(bus, frame_delay_s=0, running=0)

        self.assertEqual(
            bus.writes,
            [(0x050A, 8, 100), (0x0001, 2, 100), (0x0504, 6, 100)],
        )
        self.assertEqual([item["action"] for item in stopped], ["SKIP", "SKIP", "WROTE", "WROTE"])
        self.assertTrue(self.device._setup_done)


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
