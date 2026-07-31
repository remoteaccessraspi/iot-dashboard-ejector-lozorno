import time
from pathlib import Path
import yaml
import pymysql

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "config" / "settings.yaml"


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

def load_cfg():
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))

_cfg = load_cfg()
_db_cfg = _cfg["database"]
_relay_cfg = _cfg.get("relay", {})


# --------------------------------------------------
# DB
# --------------------------------------------------

def db_connect():
    return pymysql.connect(
        host=_db_cfg["host"],
        port=int(_db_cfg.get("port", 3306)),
        user=_db_cfg["user"],
        password=_db_cfg["password"],
        database=_db_cfg["name"],
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def latest_row(table):
    conn = db_connect()
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM `{table}` ORDER BY id DESC LIMIT 1")
        return cur.fetchone()


# --------------------------------------------------
# HYSTERESIS MEMORY
# --------------------------------------------------

relay_memory = {}  # r1: 0/1


# --------------------------------------------------
# CONDITION EVAL
# --------------------------------------------------

def check_condition(value, min_v, max_v, hyst, prev_state):
    if value is None:
        return False

    # ak bolo OFF
    if prev_state == 0:
        return min_v <= value <= max_v

    # ak bolo ON → hysterézia
    return (min_v - hyst) <= value <= (max_v + hyst)


def evaluate_rule(rule, values, prev_state):

    for cond in rule.get("conditions", []):
        src = cond["source"]
        value = values.get(src)

        if not check_condition(
            value,
            cond["min"],
            cond["max"],
            cond.get("hyst", 0),
            prev_state
        ):
            return False

    return True


def evaluate_relay(name, cfg, values):

    if cfg.get("mode") != "auto":
        return None

    prev_state = relay_memory.get(name, 0)

    rules = cfg.get("rules", [])

    for rule in rules:
        if evaluate_rule(rule, values, prev_state):
            return 1

    return 0


# --------------------------------------------------
# MAIN LOOP
# --------------------------------------------------

def main():

    print("Relay auto engine started (2s cycle)")

    while True:

        try:
            # reload config each cycle (možno zmeniť runtime)
            cfg = load_cfg()
            relay_cfg = cfg.get("relay", {}).get("control", {})

            # načítaj dáta
            irow = latest_row("current_loop") or {}
            prow = latest_row("conversion_table") or {}
            trow = latest_row("temperature") or {}

            values = {}
            values.update(irow)
            values.update(prow)
            values.update(trow)

            conn = db_connect()
            with conn.cursor() as cur:

                for name, rcfg in relay_cfg.items():

                    new_state = evaluate_relay(name, rcfg, values)

                    if new_state is None:
                        continue  # manual relay

                    old_state = relay_memory.get(name, 0)

                    if new_state != old_state:

                        relay_memory[name] = new_state

                        # update relay_state
                        cur.execute("""
                            INSERT INTO relay_state (name,state,source)
                            VALUES (%s,%s,'auto')
                            ON DUPLICATE KEY UPDATE
                            state=VALUES(state),
                            source='auto'
                        """, (name, new_state))

                        # history
                        cur.execute("""
                            INSERT INTO relay_history (name,state,source)
                            VALUES (%s,%s,'auto')
                        """, (name, new_state))

                        print(f"{name} -> {new_state}")

                # snapshot tabuľka
                cur.execute("SELECT name,state FROM relay_state")
                rows = cur.fetchall()
                states = {r["name"]: r["state"] for r in rows}

                cur.execute("""
                    INSERT INTO relay (r1,r2,r3,r4,r5,r6,r7,r8)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    states.get("r1",0),
                    states.get("r2",0),
                    states.get("r3",0),
                    states.get("r4",0),
                    states.get("r5",0),
                    states.get("r6",0),
                    states.get("r7",0),
                    states.get("r8",0),
                ))

        except Exception as e:
            print("Engine error:", e)

        time.sleep(2)


if __name__ == "__main__":
    main()
