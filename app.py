from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pathlib import Path
from datetime import datetime, timedelta

import math

import pymysql

from iot_core.core.config import load_config


# --------------------------------------------------
# INIT
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)


# --------------------------------------------------
# LOAD CONFIG
# --------------------------------------------------

def current_cfg():
    return load_config()


_cfg = current_cfg()

_hmi_cfg = _cfg.get("hmi", {})
_refresh_ms = _hmi_cfg.get("refresh_ms", 2000)


# --------------------------------------------------
# DB CONNECT
# --------------------------------------------------

# Údaje sa čítajú pri každom spojení, aby rotácia hesla nevyžadovala restart.
def db_connect():

    db_cfg = current_cfg()["database"]

    return pymysql.connect(
        host=db_cfg["host"],
        port=int(db_cfg.get("port", 3306)),
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["name"],
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


# --------------------------------------------------
# CHANNEL UTIL
# --------------------------------------------------

def build_channel_cfg(prefix):

    channels = current_cfg().get("channels", {})

    names = []
    units = []

    for i in range(1, 9):

        ch = channels.get(f"{prefix}{i}", {})

        names.append(ch.get("name", f"{prefix}{i}"))
        units.append(ch.get("unit", ""))

    return names, units


def pick(row, prefix):

    if not row:
        return [None] * 8

    return [row.get(f"{prefix}{i}") for i in range(1, 9)]


# --------------------------------------------------
# ROUTES
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def monitor(request: Request):

    return templates.TemplateResponse(
        "monitor.html",
        {
            "request": request,
            "refresh_ms": _refresh_ms
        }
    )


# --------------------------------------------------
# GRAPH PAGE
# --------------------------------------------------

@app.get("/graph", response_class=HTMLResponse)
def graph_page(request: Request):

    t_names, t_units = build_channel_cfg("t")
    p_names, p_units = build_channel_cfg("p")
    monitoring = (current_cfg().get("invt_gd20") or {}).get("monitoring") or {}
    ai2_label = (monitoring.get("ai2") or {}).get("alias") or "ai2_value"
    pid_label = (monitoring.get("pid_feedback") or {}).get("engineering_alias") or "pid_feedback_kpa"

    return templates.TemplateResponse(
        "graph.html",
        {
            "request": request,
            "t_names": t_names,
            "t_units": t_units,
            "p_names": p_names,
            "p_units": p_units,
            "ai2_label": ai2_label,
            "pid_label": pid_label,
        }
    )


# --------------------------------------------------
# GD20 PAGE
# --------------------------------------------------

@app.get("/gd20", response_class=HTMLResponse)
def gd20_page(request: Request):

    setpoint_min, setpoint_max = _gd20_setpoint_limits()

    return templates.TemplateResponse(
        "gd20.html",
        {
            "request": request,
            "refresh_ms": _refresh_ms,
            "setpoint_min": setpoint_min,
            "setpoint_max": setpoint_max,
        }
    )


# --------------------------------------------------
# API MONITOR
# --------------------------------------------------

@app.get("/api/latest")
def api_latest():

    db_ok = True
    conn = None
    gd20_row = None

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            cur.execute("SELECT * FROM temperature ORDER BY id DESC LIMIT 1")
            trow = cur.fetchone() or {}

            cur.execute("SELECT * FROM current_loop ORDER BY id DESC LIMIT 1")
            irow = cur.fetchone() or {}

            cur.execute("SELECT * FROM conversion_table ORDER BY id DESC LIMIT 1")
            prow = cur.fetchone() or {}

            cur.execute("SELECT ts FROM temperature ORDER BY id DESC LIMIT 1")
            r = cur.fetchone()
            t_last = r["ts"] if r else None

            cur.execute("SELECT ts FROM current_loop ORDER BY id DESC LIMIT 1")
            r = cur.fetchone()
            i_last = r["ts"] if r else None

            gd20_id = int((current_cfg().get("invt_gd20") or {}).get("slave_id", 100))
            cur.execute(
                "SELECT * FROM invt_gd20_state WHERE device_id = %s",
                (gd20_id,),
            )
            gd20_row = cur.fetchone()

            cur.execute(
                "SELECT value FROM control_state WHERE parameter = %s",
                ("gd20_setpoint_kpa",),
            )
            cmd = cur.fetchone()
            gd20_setpoint_command = None if cmd is None else cmd["value"]

    except:

        db_ok = False
        trow = {}
        irow = {}
        prow = {}
        t_last = None
        i_last = None
        gd20_row = None
        gd20_setpoint_command = None

    finally:

        if conn:
            conn.close()

    t_names, t_units = build_channel_cfg("t")
    i_names, i_units = build_channel_cfg("i")
    p_names, p_units = build_channel_cfg("p")

    return {

        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "refresh_ms": _refresh_ms,
        "db_status": "OK" if db_ok else "ERR",

        "t": pick(trow, "t"),
        "i": pick(irow, "i"),
        "p": pick(prow, "p"),

        "t_names": t_names,
        "t_units": t_units,

        "i_names": i_names,
        "i_units": i_units,

        "p_names": p_names,
        "p_units": p_units,

        "t_last_db": t_last.strftime("%Y-%m-%d %H:%M:%S") if t_last else None,
        "i_last_db": i_last.strftime("%Y-%m-%d %H:%M:%S") if i_last else None,

        "gd20": gd20_payload(gd20_row, gd20_setpoint_command),
    }


def _num(value):

    if value is None:
        return None

    return float(value)


def gd20_payload(row, setpoint_command=None):

    if not row:
        return None

    updated = row.get("updated_ts")
    monitoring = (current_cfg().get("invt_gd20") or {}).get("monitoring") or {}
    ai2_alias = (monitoring.get("ai2") or {}).get("alias") or "ai2_value"

    return {
        "device_id": int(row["device_id"]),
        "online": int(row["online"]),
        "running": int(row["running"]),
        "fault_code": None if row["fault_code"] is None else int(row["fault_code"]),
        "pid_setpoint_kpa": _num(row["pid_setpoint_kpa"]),
        "setpoint_command_kpa": _num(setpoint_command),
        "pid_feedback_kpa": _num(row["pid_feedback_kpa"]),
        "ai2_alias": ai2_alias,
        "ai2_kpa": _num(row["ai2_kpa"]),
        "frequency_set_hz": _num(row["frequency_set_hz"]),
        "frequency_actual_hz": _num(row["frequency_actual_hz"]),
        "output_current_a": _num(row["output_current_a"]),
        "output_voltage_v": _num(row["output_voltage_v"]),
        "dc_bus_voltage_v": _num(row["dc_bus_voltage_v"]),
        "motor_speed_rpm": None if row["motor_speed_rpm"] is None else int(row["motor_speed_rpm"]),
        "updated_ts": updated.strftime("%Y-%m-%d %H:%M:%S") if updated else None,
    }


@app.post("/api/gd20/command")
async def gd20_command(request: Request):

    body = await request.json()
    run = body.get("run")

    if not isinstance(run, bool):
        raise HTTPException(status_code=400, detail="run must be boolean")

    value = "1" if run else "0"
    conn = None

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO control (parameter, value, source)
                VALUES (%s, %s, 'hmi')
                """,
                ("gd20_run", value),
            )
            cur.execute(
                """
                REPLACE INTO control_state (parameter, value, source)
                VALUES (%s, %s, 'hmi')
                """,
                ("gd20_run", value),
            )

    except Exception as e:

        raise HTTPException(status_code=500, detail="command was not stored") from e

    finally:

        if conn:
            conn.close()

    return {"status": "ok", "run": 1 if run else 0}


def _gd20_setpoint_limits():

    command = (
        (current_cfg().get("invt_gd20") or {})
        .get("commands", {})
        .get("pid_reference")
        or {}
    )

    return (
        float(command.get("engineering_min", 0)),
        float(command.get("engineering_max", 1500)),
    )


@app.post("/api/gd20/setpoint")
async def gd20_setpoint(request: Request):

    body = await request.json()
    setpoint = body.get("setpoint_kpa")

    if isinstance(setpoint, bool) or not isinstance(setpoint, (int, float)):
        raise HTTPException(status_code=400, detail="setpoint_kpa must be a number")

    setpoint = float(setpoint)

    if not math.isfinite(setpoint):
        raise HTTPException(status_code=400, detail="setpoint_kpa must be a number")

    low, high = _gd20_setpoint_limits()

    if setpoint < low or setpoint > high:
        raise HTTPException(
            status_code=400,
            detail=f"setpoint_kpa must be {low:g}..{high:g}",
        )

    value = format(setpoint, "f").rstrip("0").rstrip(".") or "0"
    conn = None

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO control (parameter, value, source)
                VALUES (%s, %s, 'hmi')
                """,
                ("gd20_setpoint_kpa", value),
            )
            cur.execute(
                """
                REPLACE INTO control_state (parameter, value, source)
                VALUES (%s, %s, 'hmi')
                """,
                ("gd20_setpoint_kpa", value),
            )

    except Exception as e:

        raise HTTPException(status_code=500, detail="setpoint was not stored") from e

    finally:

        if conn:
            conn.close()

    return {"status": "ok", "setpoint_kpa": setpoint}


# --------------------------------------------------
# GRAPH SQL
# --------------------------------------------------

SQL_JOIN = """
SELECT
    t.ts,
    t.t1,t.t2,t.t3,t.t4,t.t5,t.t6,t.t7,t.t8,
    p.p1,p.p2,p.p3,p.p4,p.p5,p.p6,p.p7,p.p8,
    g.ai2_kpa,
    g.pid_feedback_kpa
FROM temperature t
LEFT JOIN (
    SELECT c.ts, c.p1, c.p2, c.p3, c.p4, c.p5, c.p6, c.p7, c.p8
    FROM conversion_table c
    INNER JOIN (
        SELECT ts, MAX(id) AS id
        FROM conversion_table
        GROUP BY ts
    ) latest ON latest.id = c.id
) p ON p.ts = t.ts
LEFT JOIN (
    SELECT src.ts, src.ai2_kpa, src.pid_feedback_kpa
    FROM invt_gd20 src
    INNER JOIN (
        SELECT ts, MAX(id) AS id
        FROM invt_gd20
        WHERE device_id = %s
        GROUP BY ts
    ) latest_g ON latest_g.id = src.id
) g ON g.ts = t.ts
WHERE t.ts >= %s
ORDER BY t.ts
"""


def _gd20_device_id():

    return int((current_cfg().get("invt_gd20") or {}).get("slave_id", 100))


def _downsample_rows(rows, limit=500):

    if len(rows) <= limit:
        return rows

    step = len(rows) / limit
    picked = []

    for i in range(limit):

        start_i = int(i * step)
        end_i = max(start_i + 1, int((i + 1) * step))
        chunk = rows[start_i:end_i] or [rows[start_i]]
        chosen = chunk[0]

        for row in chunk:
            if row.get("ai2_kpa") is not None or row.get("pid_feedback_kpa") is not None:
                chosen = row
                break

        picked.append(chosen)

    return picked


def _graph_payload(rows):

    data = {
        "time": [],
        "t": {f"t{i}": [] for i in range(1, 9)},
        "p": {f"p{i}": [] for i in range(1, 9)},
        "gd20": {
            "ai2_kpa": [],
            "pid_feedback_kpa": [],
        },
    }

    for r in rows:

        ts = r.get("ts")

        data["time"].append(ts.strftime("%H:%M:%S") if ts else None)

        for i in range(1, 9):

            tv = r.get(f"t{i}")
            pv = r.get(f"p{i}")

            data["t"][f"t{i}"].append(None if tv is None else float(tv))
            data["p"][f"p{i}"].append(None if pv is None else float(pv))

        data["gd20"]["ai2_kpa"].append(_num(r.get("ai2_kpa")))
        data["gd20"]["pid_feedback_kpa"].append(_num(r.get("pid_feedback_kpa")))

    return data


# --------------------------------------------------
# GRAPH HISTORY
# --------------------------------------------------

@app.get("/api/history")
def api_history(hours: int = 24):

    start = datetime.now() - timedelta(hours=hours)

    conn = None

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            cur.execute(SQL_JOIN, (_gd20_device_id(), start))
            rows = cur.fetchall()

        return _graph_payload(_downsample_rows(rows))

    finally:

        if conn:
            conn.close()


# --------------------------------------------------
# LIVE GRAPH
# --------------------------------------------------

@app.get("/api/live")
def api_live(minutes: int = 10):

    minutes = max(1, min(int(minutes or 10), 180))

    start = datetime.now() - timedelta(minutes=minutes)

    conn = None

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            cur.execute(SQL_JOIN, (_gd20_device_id(), start))
            rows = cur.fetchall()

        return _graph_payload(_downsample_rows(rows))

    finally:

        if conn:
            conn.close()