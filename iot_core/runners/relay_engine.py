#!/usr/bin/env python3

import time
from datetime import datetime, time as dtime
from pathlib import Path

import pymysql
import yaml


# --------------------------------------------------
# PATHS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SETTINGS_PATH = BASE_DIR / "config" / "settings.yaml"


# --------------------------------------------------
# LOAD CONFIG
# --------------------------------------------------

def load_cfg():
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------
# DB
# --------------------------------------------------

def db_connect(cfg):
    db = cfg["database"]
    return pymysql.connect(
        host=db["host"],
        port=int(db.get("port", 3306)),
        user=db["user"],
        password=db["password"],
        database=db["name"],
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


# --------------------------------------------------
# TIME CHECK
# --------------------------------------------------

def parse_time_safe(tstr):
    if tstr == "24:00":
        return dtime(23, 59, 59)
    return datetime.strptime(tstr, "%H:%M").time()


def time_ok(rule_time, now):
    if not rule_time:
        return True

    try:
        t_from = parse_time_safe(rule_time["from"])
        t_to = parse_time_safe(rule_time["to"])
    except Exception:
        return False

    now_t = now.time()

    # normálny interval
    if t_from <= t_to:
        return t_from <= now_t <= t_to

    # interval cez polnoc
    return now_t >= t_from or now_t <= t_to


# --------------------------------------------------
# CONDITIONS
# --------------------------------------------------

def cond_ok(cond, data, prev_state):
    src = cond.get("source")
    if not src:
        return False

    val = data.get(src)

    if val is None:
        return False

    min_v = cond.get("min")
    max_v = cond.get("max")
    hyst = float(cond.get("hyst", 0) or 0)

    # OFF -> ON len v základnom intervale min..max
    # ON -> OFF až po opustení rozšíreného pásma (hysterézia)
    if int(prev_state or 0) == 0:
        low = min_v
        high = max_v
    else:
        low = None if min_v is None else (min_v - hyst)
        high = None if max_v is None else (max_v + hyst)

    if low is not None and val < low:
        return False

    if high is not None and val > high:
        return False

    return True


# --------------------------------------------------
# LOAD LAST VALUES
# --------------------------------------------------

def read_latest(conn):
    out = {}

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM temperature ORDER BY id DESC LIMIT 1")
        t = cur.fetchone() or {}

        cur.execute("SELECT * FROM conversion_table ORDER BY id DESC LIMIT 1")
        p = cur.fetchone() or {}

        cur.execute("SELECT * FROM current_loop ORDER BY id DESC LIMIT 1")
        i = cur.fetchone() or {}

    for n in range(1, 9):
        out[f"t{n}"] = t.get(f"t{n}")
        out[f"p{n}"] = p.get(f"p{n}")
        out[f"i{n}"] = i.get(f"i{n}")

    return out


# --------------------------------------------------
# RELAY STATE HELPERS
# --------------------------------------------------

def get_relay_row(conn, name):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT name, state, source
            FROM relay_state
            WHERE name=%s
            LIMIT 1
        """, (name,))
        return cur.fetchone()


def set_relay_state(conn, name, state, source):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO relay_state(name, state, source)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                state = VALUES(state),
                source = VALUES(source)
        """, (name, int(state), source))


def set_relay_source_only_if_auto(conn, name, new_source="hmi"):
    """
    Pri prepnutí auto -> manual necháme stav tak, ako bol,
    ale zdroj už nesmie zostať 'auto'.
    """
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE relay_state
            SET source=%s
            WHERE name=%s AND source='auto'
        """, (new_source, name))


# --------------------------------------------------
# RELAY EVALUATION
# --------------------------------------------------

def eval_relay(rcfg, data, now, prev_state=0):
    logic = str(rcfg.get("logic", "OR")).upper()
    rules = rcfg.get("rules", [])

    if logic not in ("OR", "AND"):
        logic = "OR"

    final = False if logic == "OR" else True

    for rule in rules:
        t_ok = time_ok(rule.get("time"), now)
        c_ok = all(cond_ok(c, data, prev_state) for c in rule.get("conditions", []))
        active = t_ok and c_ok

        if logic == "OR":
            final = final or active
        else:
            final = final and active

    return int(final)


# --------------------------------------------------
# MAIN LOOP
# --------------------------------------------------

def main():
    cfg = load_cfg()
    conn = db_connect(cfg)

    last_mtime = 0
    relay_cfg = {}

    print("Relay engine started")
    print("SETTINGS_PATH =", SETTINGS_PATH)

    while True:
        now = datetime.now()

        # -----------------------------
        # CONFIG RELOAD
        # -----------------------------
        try:
            mtime = SETTINGS_PATH.stat().st_mtime

            if mtime != last_mtime:
                cfg = load_cfg()
                relay_cfg = cfg.get("relay", {}).get("control", {})
                last_mtime = mtime

                print("Config reloaded")
                for name, rcfg in relay_cfg.items():
                    print(f"  {name}: mode={rcfg.get('mode')}")
        except Exception as e:
            print("Config reload error:", e)

        # -----------------------------
        # DB RECONNECT
        # -----------------------------
        try:
            conn.ping(reconnect=True)
        except Exception:
            print("DB reconnect")
            conn = db_connect(cfg)

        # -----------------------------
        # LOAD DATA
        # -----------------------------
        try:
            data = read_latest(conn)
        except Exception as e:
            print("Read latest error:", e)
            time.sleep(1)
            continue

        # -----------------------------
        # RELAY EVALUATION
        # -----------------------------
        for name, rcfg in relay_cfg.items():
            mode = str(rcfg.get("mode", "manual")).lower()

            # manual režim:
            # nevyhodnocovať rules,
            # len ak ostal historicky source='auto', prepni ho späť na hmi
            if mode != "auto":
                try:
                    row = get_relay_row(conn, name)

                    if row and row.get("source") == "auto":
                        set_relay_source_only_if_auto(conn, name, "hmi")
                        print(f"{name} manual -> source auto -> hmi")
                except Exception as e:
                    print(f"{name} manual sync error:", e)

                continue

            # auto režim
            try:
                row = get_relay_row(conn, name)

                old_state = int(row["state"]) if row and row.get("state") is not None else None
                old_source = row.get("source") if row else None
                prev_state = old_state if old_state is not None else 0
                final = eval_relay(rcfg, data, now, prev_state=prev_state)
                print(
                    f"{name} hysteresis context: "
                    f"prev_state={prev_state} "
                    f"({'ON-band' if prev_state == 1 else 'OFF-band'})"
                )

                # zapisuj len keď sa niečo zmenilo
                if old_state != final or old_source != "auto":
                    set_relay_state(conn, name, final, "auto")
                    print(f"{name} => FINAL: {final} (updated)")
                else:
                    print(f"{name} => FINAL: {final} (no change)")

            except Exception as e:
                print(f"{name} eval error:", e)

        time.sleep(1)


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    main()