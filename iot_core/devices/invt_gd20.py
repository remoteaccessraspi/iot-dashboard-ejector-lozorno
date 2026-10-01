import time

from iot_core.devices.base_device import BaseDevice
from iot_core.modbus.compat import call_with_fallback


# Súvislý blok 0x3000..0x3009. Power a torque sa neukladajú, ale ležia medzi registrami.
_BLOCK_KEYS = (
    "running_frequency",
    "set_frequency",
    "dc_bus_voltage",
    "output_voltage",
    "output_current",
    "motor_speed",
    "output_power",
    "output_torque",
    "pid_setting",
    "pid_feedback",
)

def _decode(raw, reg):

    value = int(raw)

    if reg.get("signed") and value >= 0x8000:
        value -= 0x10000

    return value * float(reg["scale"])


def _non_negative(value):

    if value is None or value < 0:
        return None

    return value


def kpa_to_pid_raw(kpa, command):

    if kpa is None:
        return None

    kpa = float(kpa)

    if kpa != kpa or kpa == float("inf") or kpa == float("-inf"):
        return None

    k0 = float(command["engineering_min"])
    k1 = float(command["engineering_max"])
    r0 = int(command["raw_min"])
    r1 = int(command["raw_max"])

    if k1 == k0 or kpa < k0 or kpa > k1:
        return None

    raw = int(round((kpa - k0) / (k1 - k0) * (r1 - r0) + r0))

    if raw < r0 or raw > r1:
        return None

    return raw


def percent_to_kpa(percent, pressure):

    if percent is None:
        return None

    p0 = float(pressure["feedback_min_percent"])
    p1 = float(pressure["feedback_max_percent"])
    k0 = float(pressure["min_kpa"])
    k1 = float(pressure["max_kpa"])

    if p1 == p0:
        return None

    kpa = k0 + (percent - p0) / (p1 - p0) * (k1 - k0)

    if kpa < k0 or kpa > k1:
        return None

    return kpa


def ai_volts_to_kpa(volts, pressure):

    if volts is None:
        return None

    v0 = float(pressure["ai_report_min_v"])
    v1 = float(pressure["ai_report_max_v"])
    i0 = float(pressure["ai_report_min_ma"])
    i1 = float(pressure["ai_report_max_ma"])
    s0 = float(pressure["signal_min_ma"])
    s1 = float(pressure["signal_max_ma"])
    k0 = float(pressure["min_kpa"])
    k1 = float(pressure["max_kpa"])

    if v1 == v0 or s1 == s0:
        return None

    ma = i0 + (volts - v0) / (v1 - v0) * (i1 - i0)
    kpa = k0 + (ma - s0) / (s1 - s0) * (k1 - k0)

    if kpa < k0 or kpa > k1:
        return None

    return kpa


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
            return attempt()
        except TypeError as e:
            last = e

    raise last


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

    return list(rr.registers)


class InvtGd20Device(BaseDevice):

    def __init__(self, slave_id, device_cfg):

        super().__init__(slave_id)

        self.device_cfg = device_cfg
        self.monitoring = device_cfg["monitoring"]
        self.pressure = device_cfg["pressure"]
        self.history_interval_s = float(device_cfg["polling"]["history_interval_s"])
        self._last_history_mono = None
        # Pri štarte sa existujúci gd20_run neposiela. Zapíše sa až povel, ktorý príde potom.
        self._command_seen = False
        self._command_ts = None
        self._setpoint_seen = False
        self._setpoint_ts = None

    def execute(self, client, db_conn, ts):

        try:
            values = self._read_scaled(client)
        except Exception as e:
            print("GD20 Modbus call failed:", e)
            self._set_offline(db_conn)
            return

        if values is None:
            print("GD20 OFFLINE")
            self._set_offline(db_conn)
            return

        print(
            "GD20",
            f"ts={ts}",
            f"f={values['frequency_actual_hz']}",
            f"fset={values['frequency_set_hz']}",
            f"dc={values['dc_bus_voltage_v']}",
            f"V={values['output_voltage_v']}",
            f"I={values['output_current_a']}",
            f"rpm={values['motor_speed_rpm']}",
            f"sp={values['pid_setpoint_kpa']}",
            f"fb={values['pid_feedback_kpa']}",
            f"ai2={values['ai2_kpa']}",
            f"fault={values['fault_code']}",
            f"run={values['running']}",
        )

        try:
            self._apply_pending_command(client, db_conn)
            self._apply_pending_setpoint(client, db_conn)
            self._upsert_state(db_conn, values)
            self._insert_history_if_due(db_conn, ts, values)
        except Exception as e:
            print("GD20 DB WRITE ERROR:", e)
            try:
                db_conn.rollback()
            except Exception:
                pass

    def _read_scaled(self, client):

        block = self._read_block(client)

        if block is None:
            return None

        time.sleep(0.03)

        ai2_reg = self.monitoring["ai2"]
        ai2_raw = _read_holding(
            client,
            int(ai2_reg["address"]),
            1,
            self.slave_id,
        )

        time.sleep(0.03)

        fault_reg = self.monitoring["fault_code"]
        fault_raw = _read_holding(
            client,
            int(fault_reg["address"]),
            1,
            self.slave_id,
        )

        frequency_actual = _non_negative(
            _decode(block["running_frequency"], self.monitoring["running_frequency"])
        )
        frequency_set = _non_negative(
            _decode(block["set_frequency"], self.monitoring["set_frequency"])
        )

        pid_set_percent = _decode(block["pid_setting"], self.monitoring["pid_setting"])
        pid_fb_percent = _decode(block["pid_feedback"], self.monitoring["pid_feedback"])

        ai2_kpa = None
        if ai2_raw is not None:
            volts = _decode(ai2_raw[0], ai2_reg)
            ai2_kpa = ai_volts_to_kpa(volts, self.pressure)

        fault_code = None
        if fault_raw is not None:
            fault_code = int(round(_decode(fault_raw[0], fault_reg)))

        rpm = _non_negative(
            _decode(block["motor_speed"], self.monitoring["motor_speed"])
        )
        if rpm is not None:
            rpm = int(round(rpm))

        # Mapa nemá register RUN/STOP. Bežiaci výstup je nenulová skutočná frekvencia.
        running = 1 if frequency_actual is not None and frequency_actual > 0 else 0

        return {
            "running": running,
            "fault_code": fault_code,
            "pid_setpoint_kpa": percent_to_kpa(pid_set_percent, self.pressure),
            "pid_feedback_kpa": percent_to_kpa(pid_fb_percent, self.pressure),
            "ai2_kpa": ai2_kpa,
            "frequency_set_hz": frequency_set,
            "frequency_actual_hz": frequency_actual,
            "output_current_a": _non_negative(
                _decode(block["output_current"], self.monitoring["output_current"])
            ),
            "output_voltage_v": _non_negative(
                _decode(block["output_voltage"], self.monitoring["output_voltage"])
            ),
            "dc_bus_voltage_v": _non_negative(
                _decode(block["dc_bus_voltage"], self.monitoring["dc_bus_voltage"])
            ),
            "motor_speed_rpm": rpm,
            "fault_read_ok": fault_raw is not None,
            "ai2_read_ok": ai2_raw is not None,
        }

    def _read_block(self, client):

        regs = [self.monitoring[key] for key in _BLOCK_KEYS]
        base = int(regs[0]["address"])

        if any(int(reg["address"]) != base + index for index, reg in enumerate(regs)):
            print("GD20 monitoring addresses are not contiguous")
            return None

        raw = _read_holding(client, base, len(regs), self.slave_id)

        if raw is None:
            return None

        return {key: raw[index] for index, key in enumerate(_BLOCK_KEYS)}

    def _apply_pending_command(self, client, db_conn):

        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT value, updated_ts
                    FROM control_state
                    WHERE parameter = %s
                    """,
                    ("gd20_run",),
                )
                row = cur.fetchone()
        except Exception as e:
            print("GD20 command read error:", e)
            return

        if not self._command_seen:
            self._command_seen = True
            self._command_ts = row[1] if row else None
            return

        if row is None or row[1] == self._command_ts:
            return

        value = str(row[0]).strip()
        control = self.device_cfg["commands"]["control"]
        values = control["values"]

        if value == "1":
            raw = int(values["run_forward"])
            label = "RUN"
        elif value == "0":
            raw = int(values["stop"])
            label = "STOP"
        else:
            print("GD20 command ignored:", value)
            self._command_ts = row[1]
            return

        time.sleep(0.03)

        try:
            rr = _write_register(
                client,
                int(control["address"]),
                raw,
                self.slave_id,
            )
        except Exception as e:
            print("GD20 command write failed:", e)
            return

        if not rr or (hasattr(rr, "isError") and rr.isError()):
            print("GD20 command write error:", rr)
            return

        self._command_ts = row[1]
        print(f"GD20 command {label} -> 0x{int(control['address']):04X} = 0x{raw:04X}")

    def _apply_pending_setpoint(self, client, db_conn):

        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT value, updated_ts
                    FROM control_state
                    WHERE parameter = %s
                    """,
                    ("gd20_setpoint_kpa",),
                )
                row = cur.fetchone()
        except Exception as e:
            print("GD20 setpoint read error:", e)
            return

        if not self._setpoint_seen:
            self._setpoint_seen = True
            self._setpoint_ts = row[1] if row else None
            return

        if row is None or row[1] == self._setpoint_ts:
            return

        command = self.device_cfg["commands"]["pid_reference"]

        try:
            kpa = float(str(row[0]).strip())
        except ValueError:
            print("GD20 setpoint ignored:", row[0])
            self._setpoint_ts = row[1]
            return

        raw = kpa_to_pid_raw(kpa, command)

        if raw is None:
            print("GD20 setpoint ignored:", row[0])
            self._setpoint_ts = row[1]
            return

        time.sleep(0.03)

        try:
            rr = _write_register(
                client,
                int(command["address"]),
                raw,
                self.slave_id,
            )
        except Exception as e:
            print("GD20 setpoint write failed:", e)
            return

        if not rr or (hasattr(rr, "isError") and rr.isError()):
            print("GD20 setpoint write error:", rr)
            return

        self._setpoint_ts = row[1]
        print(f"GD20 setpoint {kpa:g} kPa -> 0x{int(command['address']):04X} = {raw}")

    def _set_offline(self, db_conn):

        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE invt_gd20_state
                    SET online = 0
                    WHERE device_id = %s
                    """,
                    (self.slave_id,),
                )
        except Exception as e:
            print("GD20 offline write error:", e)

    def _upsert_state(self, db_conn, values):

        columns = [
            "device_id",
            "online",
            "running",
            "pid_setpoint_kpa",
            "pid_feedback_kpa",
            "frequency_set_hz",
            "frequency_actual_hz",
            "output_current_a",
            "output_voltage_v",
            "dc_bus_voltage_v",
            "motor_speed_rpm",
        ]
        params = [
            self.slave_id,
            1,
            values["running"],
            values["pid_setpoint_kpa"],
            values["pid_feedback_kpa"],
            values["frequency_set_hz"],
            values["frequency_actual_hz"],
            values["output_current_a"],
            values["output_voltage_v"],
            values["dc_bus_voltage_v"],
            values["motor_speed_rpm"],
        ]

        if values["ai2_read_ok"]:
            columns.append("ai2_kpa")
            params.append(values["ai2_kpa"])

        if values["fault_read_ok"]:
            columns.append("fault_code")
            params.append(values["fault_code"])

        assignments = ", ".join(f"{column} = VALUES({column})" for column in columns if column != "device_id")
        placeholders = ", ".join(["%s"] * len(columns))

        sql = f"""
            INSERT INTO invt_gd20_state ({", ".join(columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {assignments}
        """

        with db_conn.cursor() as cur:
            cur.execute(sql, params)

    def _insert_history_if_due(self, db_conn, ts, values):

        now = time.monotonic()

        if (
            self._last_history_mono is not None
            and (now - self._last_history_mono) < self.history_interval_s
        ):
            return

        columns = [
            "ts",
            "device_id",
            "running",
            "pid_setpoint_kpa",
            "pid_feedback_kpa",
            "frequency_set_hz",
            "frequency_actual_hz",
            "output_current_a",
            "output_voltage_v",
            "dc_bus_voltage_v",
            "motor_speed_rpm",
        ]
        params = [
            ts,
            self.slave_id,
            values["running"],
            values["pid_setpoint_kpa"],
            values["pid_feedback_kpa"],
            values["frequency_set_hz"],
            values["frequency_actual_hz"],
            values["output_current_a"],
            values["output_voltage_v"],
            values["dc_bus_voltage_v"],
            values["motor_speed_rpm"],
        ]

        if values["ai2_read_ok"]:
            columns.append("ai2_kpa")
            params.append(values["ai2_kpa"])

        if values["fault_read_ok"]:
            columns.append("fault_code")
            params.append(values["fault_code"])

        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"""
            INSERT INTO invt_gd20 ({", ".join(columns)})
            VALUES ({placeholders})
        """

        with db_conn.cursor() as cur:
            cur.execute(sql, params)

        self._last_history_mono = now
        print("GD20 history insert", ts)
