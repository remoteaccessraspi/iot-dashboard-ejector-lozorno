from iot_core.devices.base_device import BaseDevice


def _call_with_fallback(fn, address: int, count: int, unit_id: int):

    tries = [
        ((), {"address": address, "count": count, "device_id": unit_id}),
        ((), {"address": address, "count": count, "unit": unit_id}),
        ((), {"address": address, "count": count, "slave": unit_id}),
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


def compute_pressure(i, a, b):

    if i is None:
        return None

    # clamp 4–20 mA
    if i < 4.0:
        i = 4.0
    if i > 20.0:
        i = 20.0

    scale = (i - 4.0) / 16.0
    return a + scale * (b - a)


class CurrentLoopDevice(BaseDevice):

    def __init__(self, slave_id, reg_cfg, conversion_cfg):

        super().__init__(slave_id)

        self.reg_cfg = reg_cfg
        self.conversion_cfg = conversion_cfg

        # mapovanie p -> index i
        self.conv_map = {}

        for p_name, cfg in conversion_cfg["channels"].items():

            src = cfg["source"]

            i_index = int(src[1:]) - 1
            p_index = int(p_name[1:]) - 1

            self.conv_map[p_index] = {
                "i_index": i_index,
                "a": cfg["a"],
                "b": cfg["b"]
            }

    def execute(self, client, db_conn, ts):

        rr = _call_with_fallback(
            getattr(client, f"read_{self.reg_cfg['function']}"),
            address=self.reg_cfg["address"],
            count=self.reg_cfg["count"],
            unit_id=self.slave_id
        )

        if not rr or (hasattr(rr, "isError") and rr.isError()):
            print("Current read error:", rr)
            return

        regs = rr.registers

        if self.reg_cfg.get("signed", False):
            regs = [(v - 0x10000 if v >= 0x8000 else v) for v in regs]

        currents = [v * self.reg_cfg["scale"] for v in regs]

        if not currents:
            print("No current values")
            return

        pressures = [None] * 8

        for p_index, conv in self.conv_map.items():

            i_index = conv["i_index"]

            if i_index >= len(currents):
                continue

            i_val = currents[i_index]

            pressures[p_index] = compute_pressure(
                i_val,
                conv["a"],
                conv["b"]
            )

        print("currents:", currents)
        print("pressures:", pressures)
        print("ts:", ts)

        try:

            with db_conn.cursor() as cur:

                # zapis prúdy
                cur.execute("""
                    INSERT INTO current_loop
                    (ts,i1,i2,i3,i4,i5,i6,i7,i8)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (ts, *currents))

                current_loop_id = cur.lastrowid

                # zapis tlaky
                cur.execute("""
                    INSERT INTO conversion_table
                    (ts,current_loop_id,p1,p2,p3,p4,p5,p6,p7,p8)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (ts, current_loop_id, *pressures))

            db_conn.commit()

            print("DB insert OK")

        except Exception as e:

            print("DB WRITE ERROR:", e)
            db_conn.rollback()