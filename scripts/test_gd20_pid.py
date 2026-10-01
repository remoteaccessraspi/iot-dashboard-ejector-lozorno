#!/usr/bin/env python3
"""READ-ONLY INVT GD20 PID diagnostic. Never writes a Modbus register."""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from iot_core.core.config import load_config
from iot_core.devices.invt_gd20 import _decode, ai_volts_to_kpa, percent_to_kpa
from iot_core.modbus.client import create_client
from iot_core.modbus.compat import call_with_fallback

PARAM_CODES = (
    "P00.01",
    "P00.06",
    "P09.00",
    "P09.02",
    "P09.03",
    "P09.04",
    "P09.05",
    "P09.06",
)

# Meanings documented in the project GD20 notes. Used only in the report.
PARAM_MEANING = {
    "P00.01": {0: "keypad", 1: "terminal", 2: "communication"},
    "P00.06": {7: "internal PID"},
    "P09.00": {6: "Modbus"},
    "P09.02": {0: "AI1", 1: "AI2", 2: "AI3", 3: "HDI", 4: "Modbus"},
}


def find_parameter(parameters, code):

    for reg in parameters.values():
        if reg.get("parameter") == code:
            return reg

    raise KeyError(code)


def port_holders(port):

    real = os.path.realpath(port)
    holders = []

    for target in (port, real):
        result = subprocess.run(
            ["fuser", target],
            capture_output=True,
            text=True,
        )
        text = (result.stdout or "") + " " + (result.stderr or "")

        for token in text.replace(":", " ").split():
            if token.isdigit():
                holders.append(int(token))

    return sorted(set(holders))


def print_stop_commands():

    print("The diagnostic script does not stop services.")
    print("Operator commands:")
    print("  sudo systemctl stop iot-master.service")
    print(f"  cd {ROOT} && PYTHONPATH=. .venv/bin/python scripts/test_gd20_pid.py")
    print("  sudo systemctl start iot-master.service")


def read_one(client, address, slave_id):

    try:
        rr = call_with_fallback(
            client.read_holding_registers,
            address=address,
            count=1,
            unit_id=slave_id,
        )
    except Exception as exc:
        return None, str(exc)

    if rr is None:
        return None, "no response"

    if hasattr(rr, "isError") and rr.isError():
        return None, str(rr)

    if not hasattr(rr, "registers") or len(rr.registers) != 1:
        return None, f"invalid response: {rr}"

    return int(rr.registers[0]), None


def fmt_num(value, digits):

    if value is None:
        return "n/a"

    return f"{value:.{digits}f}"


def ai_milliamps(volts, pressure):

    if volts is None:
        return None

    v0 = float(pressure["ai_report_min_v"])
    v1 = float(pressure["ai_report_max_v"])
    i0 = float(pressure["ai_report_min_ma"])
    i1 = float(pressure["ai_report_max_ma"])

    if v1 == v0:
        return None

    return i0 + (volts - v0) / (v1 - v0) * (i1 - i0)


def main():

    cfg = load_config()
    modbus = cfg["modbus"]
    gd20 = cfg["invt_gd20"]
    slave_id = int(gd20["slave_id"])
    pressure = gd20["pressure"]
    port = modbus["port"]
    holders = port_holders(port)

    if holders:
        print(f"Serial port is in use: {port}")
        print(f"PID: {', '.join(str(pid) for pid in holders)}")
        print_stop_commands()
        return 2

    parameters = gd20["parameters"]
    monitoring = gd20["monitoring"]

    try:
        client = create_client()
    except RuntimeError as exc:
        print(f"Serial port is in use: {port}")
        print(exc)
        print_stop_commands()
        return 2

    try:
        param_raw = {}

        for code in PARAM_CODES:
            reg = find_parameter(parameters, code)
            raw, error = read_one(client, int(reg["address"]), slave_id)
            param_raw[code] = (reg, raw, error)
            time.sleep(0.03)

        monitor_keys = (
            "running_frequency",
            "set_frequency",
            "pid_setting",
            "pid_feedback",
            "ai2",
            "fault_code",
        )
        monitor_raw = {}

        for key in monitor_keys:
            reg = monitoring[key]
            raw, error = read_one(client, int(reg["address"]), slave_id)
            monitor_raw[key] = (reg, raw, error)
            time.sleep(0.03)
    finally:
        client.close()

    freq_reg, freq_raw, freq_err = monitor_raw["running_frequency"]
    set_reg, set_raw, set_err = monitor_raw["set_frequency"]
    pid_set_reg, pid_set_raw, pid_set_err = monitor_raw["pid_setting"]
    pid_fb_reg, pid_fb_raw, pid_fb_err = monitor_raw["pid_feedback"]
    ai2_reg, ai2_raw, ai2_err = monitor_raw["ai2"]
    fault_reg, fault_raw, fault_err = monitor_raw["fault_code"]

    freq_hz = None if freq_err else _decode(freq_raw, freq_reg)
    set_hz = None if set_err else _decode(set_raw, set_reg)
    pid_set_percent = None if pid_set_err else _decode(pid_set_raw, pid_set_reg)
    pid_fb_percent = None if pid_fb_err else _decode(pid_fb_raw, pid_fb_reg)
    pid_set_kpa = percent_to_kpa(pid_set_percent, pressure)
    pid_fb_kpa = percent_to_kpa(pid_fb_percent, pressure)
    ai2_volts = None if ai2_err else _decode(ai2_raw, ai2_reg)
    ai2_ma = ai_milliamps(ai2_volts, pressure)
    ai2_kpa = ai_volts_to_kpa(ai2_volts, pressure)

    print("=" * 60)
    print("INVT GD20 READ-ONLY DIAGNOSTIC")
    print("=" * 60)
    print()
    print(f"Slave ID: {slave_id}")
    print()
    print("PARAMETERS")

    for code in PARAM_CODES:
        reg, raw, error = param_raw[code]
        if error:
            print(f"{code} = READ ERROR: {error}")
            continue

        scaled = _decode(raw, reg) if "scale" in reg else raw
        line = f"{code} = {scaled}"

        if "unit" in reg:
            line += f" {reg['unit']}"

        meaning = PARAM_MEANING.get(code, {}).get(int(raw))
        if meaning:
            line += f" ({meaning})"

        if "required_value" in reg:
            required = int(reg["required_value"])
            mark = "MATCH" if int(raw) == required else "DIFF"
            line += f" | required {required} {mark}"

        print(line)

    print()
    print("MONITORING")

    if freq_err:
        print(f"0x3000 running frequency = READ ERROR: {freq_err}")
    else:
        print(f"0x3000 running frequency = {fmt_num(freq_hz, 2)} Hz")

    if set_err:
        print(f"0x3001 set frequency     = READ ERROR: {set_err}")
    else:
        print(f"0x3001 set frequency     = {fmt_num(set_hz, 2)} Hz")

    if pid_set_err:
        print(f"0x3008 PID setting       = READ ERROR: {pid_set_err}")
    else:
        print(
            "0x3008 PID setting       = "
            f"raw {pid_set_raw} / {fmt_num(pid_set_percent, 1)} % / {fmt_num(pid_set_kpa, 1)} kPa"
        )

    if pid_fb_err:
        print(f"0x3009 PID feedback      = READ ERROR: {pid_fb_err}")
    else:
        print(
            "0x3009 PID feedback      = "
            f"raw {pid_fb_raw} / {fmt_num(pid_fb_percent, 1)} % / {fmt_num(pid_fb_kpa, 1)} kPa"
        )

    if ai2_err:
        print(f"0x300D AI2               = READ ERROR: {ai2_err}")
    else:
        print(
            "0x300D AI2               = "
            f"raw {ai2_raw} / {fmt_num(ai2_volts, 2)} V / {fmt_num(ai2_ma, 2)} mA / {fmt_num(ai2_kpa, 1)} kPa"
        )

    if fault_err:
        print(f"0x5000 fault             = READ ERROR: {fault_err}")
    else:
        print(f"0x5000 fault             = {fault_raw}")

    print()
    print("DIAGNOSTIC")
    print("AI2 raw:", "ERROR" if ai2_err else ai2_raw)
    print("AI2 converted:", "ERROR" if ai2_err else f"{fmt_num(ai2_volts, 2)} V / {fmt_num(ai2_ma, 2)} mA")
    print("AI2 kPa:", "ERROR" if ai2_err else fmt_num(ai2_kpa, 1))
    print()
    print("PID feedback raw:", "ERROR" if pid_fb_err else pid_fb_raw)
    print("PID feedback %:", "ERROR" if pid_fb_err else fmt_num(pid_fb_percent, 1))
    print("PID feedback kPa:", "ERROR" if pid_fb_err else fmt_num(pid_fb_kpa, 1))
    print()
    print("PID setting raw:", "ERROR" if pid_set_err else pid_set_raw)
    print("PID setting %:", "ERROR" if pid_set_err else fmt_num(pid_set_percent, 1))
    print("PID setpoint kPa:", "ERROR" if pid_set_err else fmt_num(pid_set_kpa, 1))
    print()
    print("AI2 valid:", "YES" if ai2_kpa is not None else "NO")
    print("PID feedback active:", "YES" if pid_fb_percent not in (None, 0) else "NO")

    if ai2_kpa is not None and pid_fb_kpa is not None:
        print(f"AI2 vs PID feedback difference: {ai2_kpa - pid_fb_kpa:.1f} kPa")
    else:
        print("AI2 vs PID feedback difference: n/a")

    print()
    print("=" * 60)
    print("NO VALUES WERE WRITTEN TO GD20")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
