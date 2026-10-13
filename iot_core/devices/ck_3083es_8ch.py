from iot_core.devices.base_device import BaseDevice


# CK-3083ES_8CH, 8× PT100.
MODEL = "CK-3083ES_8CH"


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


class Ck3083es8chDevice(BaseDevice):

    model = MODEL

    def __init__(self, slave_id, reg_cfg):

        super().__init__(slave_id)

        self.reg_cfg = reg_cfg


    def execute(self, client, db_conn, ts):

        try:
            rr = _call_with_fallback(
                getattr(client, f"read_{self.reg_cfg['function']}"),
                address=self.reg_cfg["address"],
                count=self.reg_cfg["count"],
                unit_id=self.slave_id
            )
        except Exception as e:
            print(f"{self.model} Modbus call failed:", e)
            return

        if not rr or (hasattr(rr, "isError") and rr.isError()):
            print(f"{self.model} read error:", rr)
            return

        if not hasattr(rr, "registers"):
            print(f"{self.model} invalid response:", rr)
            return

        if len(rr.registers) != self.reg_cfg["count"]:
            print(f"{self.model} wrong register count:", rr.registers)
            return

        regs = rr.registers

        # signed conversion
        if self.reg_cfg.get("signed", False):
            regs = [(v - 0x10000 if v >= 0x8000 else v) for v in regs]

        scale = self.reg_cfg["scale"]

        temps = []

        for v in regs:

            val = v * scale

            # -999.0 je invalid hodnota z modulu
            if abs(val - (-999.0)) < 1e-6:
                temps.append(None)
            else:
                temps.append(val)

        # doplnenie na 8 kanálov
        while len(temps) < 8:
            temps.append(None)

        try:

            with db_conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO temperature
                    (ts,t1,t2,t3,t4,t5,t6,t7,t8)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (ts, *temps))

        except Exception as e:

            print(f"{self.model} DB error:", e)
            return
