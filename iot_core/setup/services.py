import subprocess
import threading
import time

UNITS = ("iot-master", "iot-db-archive", "iot-dashboard")


def started_at(units=UNITS):

    """Unix čas posledného štartu služieb. None, keď sa nedá zistiť."""

    try:
        out = subprocess.run(
            ["systemctl", "show", *units, "-p", "ActiveEnterTimestamp", "--value", "--timestamp=unix"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None

    stamps = [line.strip().lstrip("@") for line in out.splitlines() if line.strip()]

    if len(stamps) != len(units):
        return None

    try:
        return {unit: float(stamp) for unit, stamp in zip(units, stamps)}
    except ValueError:
        return None


def restart_pending(entries, starts):

    """Je po poslednom štarte niektorej služby zápis, ktorý chce reštart?"""

    if not starts:
        return False

    oldest = min(starts.values())
    return any(e.get("restart") and float(e.get("ts", 0)) > oldest for e in entries)


def _restart(unit):

    subprocess.run(["sudo", "-n", "systemctl", "restart", unit], timeout=60, check=True)


def restart_all(delay_s=1.0):

    """Master a archív hneď, dashboard v pozadí, aby HTTP odpoveď stihla odísť."""

    _restart("iot-master")
    _restart("iot-db-archive")

    def later():
        time.sleep(delay_s)
        try:
            _restart("iot-dashboard")
        except Exception as e:
            print("setup restart iot-dashboard:", e)

    threading.Thread(target=later, daemon=True).start()
