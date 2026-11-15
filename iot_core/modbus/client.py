import time

from pymodbus.client import ModbusSerialClient
from iot_core.core.config import load_config

# Platí, keď v modbus chýba timeout_sec. Rovnaké číslo ako dnes v common.yaml.
DEFAULT_TIMEOUT_S = 0.55


def timeout_sec(modbus_cfg):

    return float((modbus_cfg or {}).get("timeout_sec", DEFAULT_TIMEOUT_S))


def create_client():
    cfg = load_config()["modbus"]

    client = ModbusSerialClient(
        port=cfg["port"],
        baudrate=int(cfg["baudrate"]),
        parity=str(cfg.get("parity", "N")),
        stopbits=int(cfg.get("stopbits", 1)),
        timeout=timeout_sec(cfg),
    )

    if not client.connect():
        raise RuntimeError("Modbus connection failed")

    return client


def wait_for_client(retry_sec=5.0):
    """Retry serial open until FTDI/USB is available (boot / replug)."""

    attempt = 0

    while True:
        attempt += 1

        try:
            client = create_client()
            print(f"Modbus connect OK (attempt {attempt})")
            return client

        except Exception as e:
            print(f"Modbus connect failed (attempt {attempt}): {e}")
            time.sleep(retry_sec)
