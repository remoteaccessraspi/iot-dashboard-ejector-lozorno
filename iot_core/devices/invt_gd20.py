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


def gd20_is_running(status_code, running_values=(1, 2)):

    if status_code is None:
        return None

    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return None

    return code in {int(value) for value in running_values}


def gd20_setup_items(device_cfg):

    setup = (device_cfg or {}).get("setup") or {}

    if not setup.get("enabled"):
        return []

    parameters = (device_cfg or {}).get("parameters") or {}
    stop_only = {str(key) for key in (setup.get("stop_only") or [])}
    items = []

    for key in setup.get("parameters") or []:
        spec = parameters.get(key)

        if not isinstance(spec, dict) or "address" not in spec or "required_value" not in spec:
            items.append({
                "key": key,
                "parameter": key,
                "address": None,
                "expected": None,
                "stop_only": key in stop_only,
                "error": "missing required_value",
            })
            continue

        items.append({
            "key": key,
            "parameter": spec.get("parameter") or key,
            "address": int(spec["address"]),
            "expected": int(spec["required_value"]),
            "stop_only": key in stop_only,
            "error": None,
        })

    return items


def _setup_result(parameter, address, expected, action, detail, actual=None):

    return {
        "parameter": parameter,
        "address": address,
        "expected": expected,
        "actual": actual,
        "action": action,
        "detail": detail,
    }


def external_stop_active(raw, stop_cfg):

    if not stop_cfg or not stop_cfg.get("enabled"):
        return None

    if raw is None:
        return None

    try:
        level = (int(raw) >> int(stop_cfg["bit"])) & 1
        active = int(stop_cfg.get("active_value", 1))
    except (TypeError, ValueError, KeyError):
        return None

    return level == active


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


def gd20_sample_age_s(updated, now):

    if updated is None or now is None:
        return None

    age = (now - updated).total_seconds()

    if age < 0:
        return 0.0

    return age


def gd20_stability(setpoint_kpa, feedback_kpa, tolerance_kpa, running, online, age_s, max_age_s):

    error = None

    if setpoint_kpa is not None and feedback_kpa is not None:
        error = float(feedback_kpa) - float(setpoint_kpa)

    fresh = (
        age_s is not None
        and max_age_s is not None
        and float(age_s) <= float(max_age_s)
    )
    stable = (
        error is not None
        and tolerance_kpa is not None
        and online
        and running
        and fresh
        and abs(error) <= float(tolerance_kpa)
    )

    return stable, error


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
        # Setpoint sa posiela, kým sa 0x3008 nezhoduje s gd20_setpoint_kpa.
        self._setpoint_seen = False
        self._setpoint_ts = None
        # Setup z configu sa dokončí raz po štarte. Ďalšie cykly ho už nečítajú.
        self._setup_done = not bool((device_cfg.get("setup") or {}).get("enabled"))

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
            f"ext={values['external_stop'] if values['external_stop'] is not None else '-'}",
            f"status={values['status_code'] if values['status_code'] is not None else '-'}",
            f"run={values['running'] if values['running'] is not None else '-'}",
        )

        try:
            if not self._setup_done:
                self.apply_setup(client, running=values["running"])
            self._apply_pending_command(client, db_conn, values["external_stop"])
            synced_kpa = self._apply_pending_setpoint(
                client,
                db_conn,
                values["pid_setpoint_kpa"],
            )
            if synced_kpa is not None:
                values["pid_setpoint_kpa"] = synced_kpa
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

        status_reg = self.monitoring.get("status_word") or {}
        status_raw = None
        if "address" in status_reg:
            time.sleep(0.03)
            status_raw = _read_holding(
                client,
                int(status_reg["address"]),
                1,
                self.slave_id,
            )
        status_code = None if status_raw is None else int(status_raw[0])
        known_running = gd20_is_running(status_code, status_reg.get("running_values") or (1, 2))
        running = None if known_running is None else (1 if known_running else 0)

        di_reg = self.monitoring.get("digital_input_state") or {}
        di_raw = None
        if "address" in di_reg:
            time.sleep(0.03)
            di_raw = _read_holding(
                client,
                int(di_reg["address"]),
                1,
                self.slave_id,
            )
        di_state = None if di_raw is None else int(di_raw[0])

        return {
            "running": running,
            "status_code": status_code,
            "status_read_ok": status_raw is not None,
            "external_stop": external_stop_active(di_state, self.device_cfg.get("external_stop")),
            "di_read_ok": di_raw is not None,
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

    def apply_setup(self, client, frame_delay_s=0.03, running=None):

        """Raz po štarte mastera. Zapíše len required_value, ktoré sa líšia."""

        if self._setup_done:
            return []

        items = gd20_setup_items(self.device_cfg)
        results = []
        pending = False

        if running is None:
            running = self._setup_running(client)

        for item in items:
            label = item["parameter"]
            address = item["address"]
            expected = item["expected"]

            if item["error"] or address is None:
                results.append(_setup_result(label, address, expected, "SKIP", item["error"]))
                pending = True
                print(f"GD20 setup {label} skipped: {item['error']}")
                continue

            if item["stop_only"] and running != 0:
                results.append(_setup_result(label, address, expected, "DEFER", "drive is not stopped"))
                pending = True
                print(f"GD20 setup {label} 0x{address:04X} deferred until STOP")
                continue

            actual_words = _read_holding(client, address, 1, self.slave_id)

            if actual_words is None:
                results.append(_setup_result(label, address, expected, "READ_ERROR", "FC03 returned no word"))
                pending = True
                print(f"GD20 setup {label} 0x{address:04X} read failed")
                continue

            actual = int(actual_words[0])

            if actual == expected:
                results.append(_setup_result(label, address, expected, "SKIP", "already matches", actual))
                print(f"GD20 setup {label} 0x{address:04X} {actual} == {expected}")
                continue

            if frame_delay_s:
                time.sleep(frame_delay_s)

            try:
                written = _write_register(client, address, expected, self.slave_id)
            except Exception as exc:
                written = None
                print(f"GD20 setup {label} 0x{address:04X} write failed: {exc}")

            if not written or (hasattr(written, "isError") and written.isError()):
                results.append(_setup_result(label, address, expected, "WRITE_FAILED", "FC06 failed", actual))
                pending = True
                print(f"GD20 setup {label} 0x{address:04X} {actual} -> {expected} WRITE_FAILED")
                continue

            if frame_delay_s:
                time.sleep(frame_delay_s)

            checked_words = _read_holding(client, address, 1, self.slave_id)
            checked = None if checked_words is None else int(checked_words[0])

            if checked != expected:
                results.append(_setup_result(label, address, expected, "VERIFY_FAILED", "read-back differs", checked))
                pending = True
                print(f"GD20 setup {label} 0x{address:04X} read-back {checked} != {expected}")
                continue

            results.append(_setup_result(label, address, expected, "WROTE", "written and verified", checked))
            print(f"GD20 setup {label} 0x{address:04X} {actual} -> {expected}")

        if not pending:
            self._setup_done = True

        return results

    def _setup_running(self, client):

        status_reg = self.monitoring.get("status_word") or {}

        if "address" not in status_reg:
            return None

        raw = _read_holding(client, int(status_reg["address"]), 1, self.slave_id)

        if raw is None:
            return None

        known = gd20_is_running(raw[0], status_reg.get("running_values") or (1, 2))

        if known is None:
            return None

        return 1 if known else 0

    def _apply_pending_command(self, client, db_conn, external_stop=None):

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
            if external_stop:
                print("GD20 RUN blocked by external stop")
                self._command_ts = row[1]
                return
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

    def _apply_pending_setpoint(self, client, db_conn, actual_kpa):

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
            return None

        if row is None:
            return None

        command = self.device_cfg["commands"]["pid_reference"]

        try:
            kpa = float(str(row[0]).strip())
        except ValueError:
            self._ignore_setpoint(row)
            return None

        raw = kpa_to_pid_raw(kpa, command)

        if raw is None:
            self._ignore_setpoint(row)
            return None

        if actual_kpa is not None and kpa_to_pid_raw(actual_kpa, command) == raw:
            self._setpoint_seen = True
            self._setpoint_ts = row[1]
            return None

        # Bez odčítaného setpointu sa starý povel pri štarte neposiela.
        if actual_kpa is None:
            if not self._setpoint_seen:
                self._setpoint_seen = True
                self._setpoint_ts = row[1]
                return None
            if row[1] == self._setpoint_ts:
                return None

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
            return None

        if not rr or (hasattr(rr, "isError") and rr.isError()):
            print("GD20 setpoint write error:", rr)
            return None

        self._setpoint_seen = True
        self._setpoint_ts = row[1]
        if actual_kpa is None:
            print(f"GD20 setpoint {kpa:g} kPa -> 0x{int(command['address']):04X} = {raw}")
        else:
            print(
                f"GD20 setpoint mismatch {actual_kpa:g} -> {kpa:g} kPa"
                f" -> 0x{int(command['address']):04X} = {raw}"
            )

        return percent_to_kpa(raw * float(command["scale"]), self.pressure)

    def _ignore_setpoint(self, row):

        if row[1] == self._setpoint_ts:
            return

        print("GD20 setpoint ignored:", row[0])
        self._setpoint_seen = True
        self._setpoint_ts = row[1]

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

        if values["di_read_ok"] and values["external_stop"] is not None:
            columns.append("external_stop")
            params.append(1 if values["external_stop"] else 0)

        if values["status_read_ok"]:
            columns.extend(("status_code", "running"))
            params.extend((values["status_code"], values["running"]))

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

        if values.get("running") is None:
            return

        if (
            self._last_history_mono is not None
            and (now - self._last_history_mono) < self.history_interval_s
        ):
            return

        columns = [
            "ts",
            "device_id",
            "running",
            "status_code",
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
            values["status_code"],
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

        if values["di_read_ok"] and values["external_stop"] is not None:
            columns.append("external_stop")
            params.append(1 if values["external_stop"] else 0)

        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"""
            INSERT INTO invt_gd20 ({", ".join(columns)})
            VALUES ({placeholders})
        """

        with db_conn.cursor() as cur:
            cur.execute(sql, params)

        self._last_history_mono = now
        print("GD20 history insert", ts)
