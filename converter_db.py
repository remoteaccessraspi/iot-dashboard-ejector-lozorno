#!/usr/bin/env python3
import time
from datetime import datetime, UTC
from pathlib import Path

import yaml
import pymysql

SETTINGS_PATH = Path(__file__).resolve().parent / "config" / "settings.yaml"


def load_cfg():
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))


def db_connect(db):
    return pymysql.connect(
        host=db["host"],
        port=int(db.get("port", 3306)),
        user=db["user"],
        password=db["password"],
        database=db["name"],
        autocommit=True,
        connect_timeout=int(db.get("connect_timeout_sec", 5)),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def compute_p(i_value, a, b):

    if i_value is None:
        return None

    i_clamped = max(4.0, min(20.0, i_value))
    scale = (i_clamped - 4.0) / 16.0

    return a + scale * (b - a)


def main():

    cfg = load_cfg()
    db = cfg["database"]

    conv = cfg.get("conversion", {})
    interval = int(conv.get("interval_sec", 5))

    channels = conv.get("channels", {})

    if not channels:
        raise RuntimeError("Missing conversion.channels in settings.yaml")

    conn = db_connect(db)

    last_id = 0

    try:

        while True:

            try:

                with conn.cursor() as cur:

                    cur.execute(
                        """
                        SELECT id, ts, i1,i2,i3,i4,i5,i6,i7,i8
                        FROM current_loop
                        WHERE id > %s
                        ORDER BY id
                        LIMIT 50
                        """,
                        (last_id,),
                    )

                    rows = cur.fetchall()

                if not rows:
                    time.sleep(interval)
                    continue

                for row in rows:

                    current_loop_id = row["id"]

                    currents = {
                        "i1": row["i1"],
                        "i2": row["i2"],
                        "i3": row["i3"],
                        "i4": row["i4"],
                        "i5": row["i5"],
                        "i6": row["i6"],
                        "i7": row["i7"],
                        "i8": row["i8"],
                    }

                    ps = {}

                    for p_name, spec in channels.items():

                        src = spec["source"]
                        a = float(spec.get("a", 1.0))
                        b = float(spec.get("b", 0.0))

                        ps[p_name] = compute_p(currents.get(src), a, b)

                    ts = row["ts"].replace(microsecond=0)

                    with conn.cursor() as cur:

                        cur.execute(
                            """
                            INSERT INTO conversion_table
                            (ts, current_loop_id, p1,p2,p3,p4,p5,p6,p7,p8)
                            VALUES
                            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (
                                ts,
                                current_loop_id,
                                ps.get("p1"),
                                ps.get("p2"),
                                ps.get("p3"),
                                ps.get("p4"),
                                ps.get("p5"),
                                ps.get("p6"),
                                ps.get("p7"),
                                ps.get("p8"),
                            ),
                        )

                    last_id = current_loop_id

                    print(
                        "OK",
                        ts,
                        "current_loop_id=",
                        current_loop_id,
                        "p1=",
                        ps.get("p1"),
                    )

            except pymysql.err.OperationalError:

                try:
                    conn.close()
                except Exception:
                    pass

                time.sleep(2)
                conn = db_connect(db)

            time.sleep(interval)

    finally:

        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()