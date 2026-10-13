import time
from datetime import datetime

from iot_core.core.config import load_config
from iot_core.db.connection import get_connection
from iot_core.modbus.client import wait_for_client

from iot_core.devices.ck_3083es_8ch import Ck3083es8chDevice
from iot_core.devices.ck_7082e_8ch import Ck7082e8chDevice
from iot_core.devices.invt_gd20 import InvtGd20Device
from iot_core.devices.em2rs_556 import Em2rs556Device, attach_boot


# --------------------------------------------------
# CONNECTION HELPERS
# --------------------------------------------------

def reconnect_client(client):

    for attempt in range(3):

        try:

            print(f"Modbus reconnect attempt {attempt+1}")

            client.close()
            time.sleep(0.3)

            if client.connect():

                print("Modbus reconnect OK")
                return True

        except Exception as e:

            print("Reconnect error:", e)

        time.sleep(0.5)

    print("Modbus reconnect FAILED")
    return False


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    cfg = load_config()

    modbus_cfg = cfg["modbus"]

    db_conn = get_connection()

    client = wait_for_client(retry_sec=5.0)

    timeout = float(modbus_cfg.get("timeout_sec", 0.3))

    if hasattr(client, "timeout"):
        client.timeout = timeout

    print("Modbus timeout:", timeout)

    # --------------------------------------------------
    # DEVICE CONFIG
    # --------------------------------------------------

    slaves_cfg = modbus_cfg["slaves"]

    ck_3083es = Ck3083es8chDevice(
        slave_id=slaves_cfg[Ck3083es8chDevice.model],
        reg_cfg=modbus_cfg["registers"][Ck3083es8chDevice.model]
    )

    ck_7082e = Ck7082e8chDevice(
        slave_id=slaves_cfg[Ck7082e8chDevice.model],
        reg_cfg=modbus_cfg["registers"][Ck7082e8chDevice.model],
        conversion_cfg=cfg["conversion"]
    )

    # --------------------------------------------------
    # POLL ORDER
    # --------------------------------------------------

    devices = [
        ck_3083es,
        ck_7082e,
    ]

    gd20_cfg = cfg.get("invt_gd20") or {}

    if gd20_cfg.get("enabled"):
        devices.append(
            InvtGd20Device(
                slave_id=int(gd20_cfg["slave_id"]),
                device_cfg=gd20_cfg,
            )
        )

    em2rs_cfg = cfg.get("em2rs_556") or {}

    if em2rs_cfg.get("enabled"):
        em2rs = Em2rs556Device(
            slave_id=int(em2rs_cfg["slave_id"]),
            device_cfg=em2rs_cfg,
        )
        attach_boot(em2rs)
        stability = (gd20_cfg.get("stability") or {})
        trim = ((em2rs_cfg.get("valve") or {}).get("p7_trim") or {})
        if gd20_cfg.get("enabled"):
            em2rs.note_gd20(
                int(gd20_cfg.get("slave_id", 100)),
                trim.get("invt_tolerance_kpa"),
                stability.get("max_age_s", 10),
            )
        devices.append(em2rs)

    print(
        f"Modbus Master started "
        f"({Ck3083es8chDevice.model}={slaves_cfg[Ck3083es8chDevice.model]}, "
        f"{Ck7082e8chDevice.model}={slaves_cfg[Ck7082e8chDevice.model]}, "
        f"GD20={gd20_cfg.get('slave_id') if gd20_cfg.get('enabled') else 'off'}, "
        f"EM2RS={em2rs_cfg.get('slave_id') if em2rs_cfg.get('enabled') else 'off'})"
    )

    print("Devices:", [getattr(d, "model", d.__class__.__name__) for d in devices])

    # --------------------------------------------------
    # POLL PARAMETERS
    # --------------------------------------------------

    PERIOD = float(modbus_cfg["poll_period_s"])
    FRAME_DELAY = 0.03

    print("Poll period:", PERIOD, "s")

    for device in devices:

        if isinstance(device, Em2rs556Device):

            try:
                device.apply_setup(client, frame_delay_s=FRAME_DELAY)
            except Exception as e:
                print("EM2RS setup failed:", e)

            time.sleep(FRAME_DELAY)

    # --------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------

    while True:

        cycle_start = time.monotonic()

        # spoločný timestamp pre všetky zariadenia
        ts = datetime.now().replace(microsecond=0)

        # -------------------------------
        # DB reconnect
        # -------------------------------

        try:
            db_conn.ping(reconnect=True)

        except Exception:

            print("Database reconnect")

            db_conn = get_connection()

        # -------------------------------
        # DEVICE POLLING
        # -------------------------------

        for device in devices:

            name = getattr(device, "model", device.__class__.__name__)

            start = time.monotonic()

            try:

                print(f"Polling {name}")

                device.execute(client, db_conn, ts)

                latency = (time.monotonic() - start) * 1000

                print(f"{name} OK {latency:.1f} ms")

            except Exception as e:

                latency = (time.monotonic() - start) * 1000

                print(f"{name} ERROR {latency:.1f} ms -> {e}")

                reconnect_client(client)

            # RTU frame spacing
            time.sleep(FRAME_DELAY)

        # -------------------------------
        # STABLE CYCLE TIMING
        # -------------------------------

        elapsed = time.monotonic() - cycle_start

        sleep_time = PERIOD - elapsed

        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            print("Cycle overrun:", round(-sleep_time, 3), "s")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:
        print("Modbus master stopped")

    except Exception as e:
        print("Fatal error:", e)