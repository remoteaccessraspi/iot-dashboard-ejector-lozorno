from iot_core.devices.base_device import BaseDevice
import time


# ==========================================================
# MODBUS TIMING
# ==========================================================

MODBUS_GAP = 0.02
READ_WRITE_PAUSE = 0.15


# ==========================================================
# READ FALLBACK
# ==========================================================

def _call_read_with_fallback(fn, address: int, count: int, unit_id: int):

    tries = [
        ((), {"address": address, "count": count, "unit": unit_id}),
        ((), {"address": address, "count": count, "slave": unit_id}),
        ((), {"address": address, "count": count, "device_id": unit_id}),
        ((address, count, unit_id), {}),
        ((address, count), {"unit": unit_id}),
        ((address, count), {"slave": unit_id}),
    ]

    last = None

    for args, kwargs in tries:
        try:
            if args:
                return fn(*args, **kwargs)
            return fn(**kwargs)
        except TypeError as e:
            last = e

    raise last


# ==========================================================
# WRITE COILS
# ==========================================================

def _call_write_coils_with_fallback(client, address, values, slave_id):

    tries = [
        lambda: client.write_coils(address, values, unit=slave_id),
        lambda: client.write_coils(address, values, slave=slave_id),
        lambda: client.write_coils(address, values, device_id=slave_id),
        lambda: client.write_coils(address, values, slave_id),
    ]

    for fn in tries:
        try:
            return fn()
        except TypeError:
            pass

    raise RuntimeError("write_coils fallback failed")


# ==========================================================
# WRITE REGISTERS
# ==========================================================

def _call_write_with_fallback(client, address, values, slave_id):

    tries = [
        lambda: client.write_registers(address, values, unit=slave_id),
        lambda: client.write_registers(address, values, slave=slave_id),
        lambda: client.write_registers(address, values, device_id=slave_id),
        lambda: client.write_registers(address, values, slave_id),
    ]

    for fn in tries:
        try:
            return fn()
        except TypeError:
            pass

    raise RuntimeError("write_registers fallback failed")


# ==========================================================
# DEVICE CLASS
# ==========================================================

class OptaPID(BaseDevice):

    def __init__(self, slave_id):
        super().__init__(slave_id)

    def execute(self, client, db_conn, ts):

        # ======================================================
        # 1 READ INPUT REGISTERS
        # ======================================================

        try:
            rr = _call_read_with_fallback(
                getattr(client, "read_input_registers"),
                address=0,
                count=5,
                unit_id=self.slave_id
            )
        except Exception as e:
            print("OPTA Modbus read failed:", e)
            return

        if not rr or (hasattr(rr, "isError") and rr.isError()):
            print("OPTA read error:", rr)
            return

        if not hasattr(rr, "registers") or len(rr.registers) != 5:
            print("OPTA invalid response:", rr)
            return

        regs = rr.registers

        # convert signed
        regs = [(v - 0x10000 if v >= 0x8000 else v) for v in regs]

        feedback = regs[0] / 10.0
        current_duty = regs[1] / 10.0

        # ======================================================
        # DB WRITE FEEDBACK
        # ======================================================

        try:

            with db_conn.cursor() as cur:

                cur.executemany(
                    """
                    REPLACE INTO relay_state(name,state,source)
                    VALUES (%s,%s,'opta')
                    """,
                    [
                        ('pid_feedback', feedback),
                        ('pwm_output', current_duty)
                    ]
                )

        except Exception as e:
            print("OPTA DB error (read):", e)

        time.sleep(READ_WRITE_PAUSE)

        # ======================================================
        # 2 READ CONTROL PARAMETERS
        # ======================================================

        params = {}

        try:

            with db_conn.cursor() as cur:

                cur.execute("""
                    SELECT parameter,value
                    FROM control
                    WHERE parameter IN (
                        'pwm_period',
                        'pwm_duty',
                        'pid_t_set',
                        'pid_t_full',
                        'pid_t_move'
                    )
                    ORDER BY ts DESC
                """)

                rows = cur.fetchall()

                for row in rows:

                    param = row[0]
                    value = row[1]

                    if param not in params:
                        params[param] = value

        except Exception as e:
            print("OPTA DB error (control read):", e)
            return

        try:

            pwm_period = int(float(params.get("pwm_period", 0)))
            pwm_duty = int(float(params.get("pwm_duty", 0)))

            t_set = float(params.get("pid_t_set", 0))
            t_full = int(float(params.get("pid_t_full", 0)))
            t_move = int(float(params.get("pid_t_move", 0)))

        except Exception as e:
            print("OPTA parameter conversion error:", e)
            return

        t_set_scaled = int(round(t_set * 10))

        values = [
            pwm_period,
            pwm_duty,
            t_set_scaled,
            t_full,
            t_move
        ]

        # ======================================================
        # 3 READ COIL STATES
        # ======================================================

        enable_pwm = False
        enable_pid = False

        try:

            with db_conn.cursor() as cur:

                cur.execute("""
                    SELECT name,state
                    FROM relay_state
                    WHERE name IN ('r1','r2')
                """)

                rows = cur.fetchall()

                state_map = {}

                for r in rows:
                    try:
                        name = r["name"]
                        state = r["state"]
                    except (TypeError, KeyError):
                        name = r[0]
                        state = r[1]

                    state_map[name] = state

                enable_pwm = bool(state_map.get("r1", 0))
                enable_pid = bool(state_map.get("r2", 0))

                print(f"RELAY DB: {state_map} -> PWM={enable_pwm} PID={enable_pid}")

        except Exception as e:

            print("OPTA DB error (coil read):", e)

            enable_pwm = False
            enable_pid = False

        # ======================================================
        # 4 WRITE COILS
        # ======================================================

        try:

            wr_coils = _call_write_coils_with_fallback(
                client,
                address=0,
                values=[enable_pwm, enable_pid],
                slave_id=self.slave_id
            )

            if hasattr(wr_coils, "isError") and wr_coils.isError():
                print("OPTA coil write error:", wr_coils)

        except Exception as e:
            print("OPTA coil write failed:", e)

        time.sleep(MODBUS_GAP)

        # ======================================================
        # 5 WRITE HOLDING REGISTERS
        # ======================================================

        try:

            wr = _call_write_with_fallback(
                client,
                address=0,
                values=values,
                slave_id=self.slave_id
            )

        except Exception as e:
            print("OPTA write failed:", e)
            return

        if hasattr(wr, "isError") and wr.isError():
            print("OPTA write error:", wr)
            return

        # ======================================================
        # 6 UPDATE CONTROL STATE
        # ======================================================

        try:

            with db_conn.cursor() as cur:

                cur.executemany(
                    """
                    REPLACE INTO control_state(parameter,value,source)
                    VALUES (%s,%s,'opta')
                    """,
                    [
                        ('pwm_period', pwm_period),
                        ('pwm_duty', pwm_duty),
                        ('pid_t_set', t_set),
                        ('pid_t_full', t_full),
                        ('pid_t_move', t_move)
                    ]
                )

        except Exception as e:
            print("OPTA DB error (control_state write):", e)