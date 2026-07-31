import time
from datetime import datetime

from iot_core.core.config import load_config
from iot_core.db.connection import get_connection
from iot_core.modbus.client import create_client

from iot_core.devices.opta_pid import OptaPID
from iot_core.devices.temperature import TemperatureDevice
from iot_core.devices.current_loop import CurrentLoopDevice
from iot_core.devices.waveshare_relay import WaveshareRelay


# --------------------------------------------------
# RELAY MODE SYNC (YAML -> DB)
# --------------------------------------------------

def sync_relay_modes(conn, relay_cfg):

    print("Sync relay modes with YAML")

    control = relay_cfg.get("control", {})

    cur = conn.cursor()

    for name, cfg in control.items():

        mode = cfg.get("mode", "manual")

        if mode == "auto":

            print("Relay", name, "-> AUTO")

            cur.execute(
                """
                UPDATE relay_state
                SET source='auto'
                WHERE name=%s
                """,
                (name,)
            )

    conn.commit()


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

    # --------------------------------------------------
    # SYNC RELAY MODES
    # --------------------------------------------------

    if "relay" in cfg:
        sync_relay_modes(db_conn, cfg["relay"])

    client = create_client()

    timeout = float(modbus_cfg.get("timeout_sec", 0.3))

    if hasattr(client, "timeout"):
        client.timeout = timeout

    print("Modbus timeout:", timeout)

    # --------------------------------------------------
    # DEVICE CONFIG
    # --------------------------------------------------

    slaves_cfg = modbus_cfg["slaves"]

    opta = OptaPID(
        slave_id=slaves_cfg["opta_slave_id"]
    )

    temperature = TemperatureDevice(
        slave_id=slaves_cfg["temperature_slave_id"],
        reg_cfg=modbus_cfg["registers"]["temperature"]
    )

    current_loop = CurrentLoopDevice(
        slave_id=slaves_cfg["current_slave_id"],
        reg_cfg=modbus_cfg["registers"]["current_loop"],
        conversion_cfg=cfg["conversion"]
    )

    waveshare_relay = WaveshareRelay(
        slave_id=slaves_cfg["waveshare_relay_slave_id"]
    )

    # --------------------------------------------------
    # POLL ORDER
    # --------------------------------------------------

    devices = [
        temperature,
        current_loop,
        opta,
        waveshare_relay
    ]

    print(
        f"Modbus Master started "
        f"(ID1={slaves_cfg['opta_slave_id']}, "
        f"ID2={slaves_cfg['temperature_slave_id']}, "
        f"ID3={slaves_cfg['current_slave_id']}, "
        f"ID4={slaves_cfg['waveshare_relay_slave_id']})"
    )

    print("Devices:", [d.__class__.__name__ for d in devices])

    # --------------------------------------------------
    # POLL PARAMETERS
    # --------------------------------------------------

    PERIOD = 5.0
    FRAME_DELAY = 0.03

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

            name = device.__class__.__name__

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