import unittest
from unittest.mock import patch

from iot_core.core.config import load_config
from iot_core.devices.ck_7082e_8ch import Ck7082e8chDevice, compute_converted
from iot_core.db import connection


class _Response:

    def __init__(self, registers):

        self.registers = registers

    def isError(self):

        return False


class _Client:

    def __init__(self, registers):

        self.registers = registers

    def read_holding_registers(self, address, count, device_id):

        return _Response(self.registers)


class _Cursor:

    lastrowid = 1

    def __enter__(self):

        return self

    def __exit__(self, exc_type, exc, tb):

        return False

    def execute(self, sql, params=None):

        return None


class _Conn:

    def cursor(self):

        return _Cursor()

    def commit(self):

        return None


class LoopLowTest(unittest.TestCase):

    def test_default_cut_is_three_and_a_half_ma(self):

        self.assertIsNone(compute_converted(3.49, 0, 1500))
        self.assertEqual(compute_converted(3.5, 0, 1500), 0)
        self.assertEqual(compute_converted(20.0, 0, 1500), 1500)

    def test_cut_follows_the_given_limit(self):

        self.assertIsNone(compute_converted(3.7, 0, 1500, low_ma=3.8))
        self.assertEqual(compute_converted(3.8, 0, 1500, low_ma=3.8), 0)

    def test_device_uses_its_limit_on_every_channel(self):

        conversion = {
            "channels": {
                "p4": {"source": "i4", "a": 0, "b": 12.5},
                "p6": {"source": "i6", "a": 0, "b": 1500.0},
            },
        }
        device = Ck7082e8chDevice(
            slave_id=3,
            reg_cfg={"function": "holding_registers", "address": 96, "count": 8, "scale": 0.001},
            conversion_cfg=conversion,
            low_ma=3.8,
        )
        printed = []
        currents = [0, 0, 0, 3700, 0, 20000, 0, 0]

        with patch("builtins.print", side_effect=lambda *a: printed.append(a)):
            device.execute(_Client(currents), _Conn(), None)

        converted = next(args[1] for args in printed if args[0] == "converted:")
        self.assertIsNone(converted[3])
        self.assertEqual(converted[5], 1500.0)

    def test_register_is_signed_int16(self):

        reg = load_config()["modbus"]["registers"]["CK-7082E_8CH"]
        device = Ck7082e8chDevice(
            slave_id=3,
            reg_cfg=reg,
            conversion_cfg={"channels": {}},
        )
        printed = []
        words = [0xF6D7, 4000, 12000, 20000, 0, 0, 0, 0]

        with patch("builtins.print", side_effect=lambda *a: printed.append(a)):
            device.execute(_Client(words), _Conn(), None)

        currents = next(args[1] for args in printed if args[0] == "currents:")
        self.assertAlmostEqual(currents[0], -2.345)
        self.assertAlmostEqual(currents[1], 4.0)
        self.assertAlmostEqual(currents[3], 20.0)


class DbPortTest(unittest.TestCase):

    def test_missing_port_goes_to_the_ram_instance(self):

        cfg = {"database": {"host": "127.0.0.1", "user": "u", "password": "p", "name": "ejector"}}

        with patch.object(connection, "load_config", return_value=cfg), \
             patch.object(connection.pymysql, "connect") as connect:
            connection.get_connection()

        self.assertEqual(connect.call_args.kwargs["port"], 3307)


if __name__ == "__main__":
    unittest.main()
