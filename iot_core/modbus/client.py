from pymodbus.client import ModbusSerialClient
from iot_core.core.config import load_config

def create_client():
    cfg = load_config()["modbus"]

    client = ModbusSerialClient(
        port=cfg["port"],
        baudrate=int(cfg["baudrate"]),
        parity=str(cfg.get("parity", "N")),
        stopbits=int(cfg.get("stopbits", 1)),
        timeout=float(cfg.get("timeout_sec", 1.0)),
    )

    if not client.connect():
        raise RuntimeError("Modbus connection failed")

    return client
