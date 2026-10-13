from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pathlib import Path
from datetime import datetime, timedelta
import time

import math

import pymysql

from iot_core.core.config import load_config
from iot_core.devices.em2rs_556 import settle_remaining_s
from iot_core.devices.invt_gd20 import gd20_is_running, gd20_sample_age_s, gd20_stability


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


def _name_is_na(value):

    if not isinstance(value, str):
        return False

    text = value.strip().lower()
    return text == "" or text == "na"


def _register_hidden(reg):

    if not isinstance(reg, dict):
        return False

    if _name_is_na(reg.get("alias")):
        return True

    if "engineering_alias" in reg and _name_is_na(reg.get("engineering_alias")):
        return True

    return False


# Riadok karty GD20 a register, ktorého alias ho skrýva.
_GD20_CARD_ROWS = (
    ("setpoint", "monitoring", "pid_setting"),
    ("setpoint_command", "commands", "pid_reference"),
    ("pid_feedback", "monitoring", "pid_feedback"),
    ("ai2", "monitoring", "ai2"),
    ("frequency", "monitoring", "running_frequency"),
    ("frequency_set", "monitoring", "set_frequency"),
    ("current", "monitoring", "output_current"),
    ("voltage", "monitoring", "output_voltage"),
    ("dc_bus", "monitoring", "dc_bus_voltage"),
    ("speed", "monitoring", "motor_speed"),
)


def gd20_row_visible(cfg):

    gd20 = (cfg or {}).get("invt_gd20") or {}
    visible = {}

    for key, section, name in _GD20_CARD_ROWS:
        reg = ((gd20.get(section) or {}).get(name) or {})
        visible[key] = not _register_hidden(reg)

    return visible


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
    cfg = current_cfg()
    monitoring = (cfg.get("invt_gd20") or {}).get("monitoring") or {}
    visible = gd20_row_visible(cfg)
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
            "show_gd20_ai2": visible["ai2"],
            "show_gd20_pid": visible["pid_feedback"],
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
    em2rs_row = None
    em2rs_sample_ts = None

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

            cur.execute(
                "SELECT value FROM control_state WHERE parameter = %s",
                ("em2rs_p7_setpoint_kpa",),
            )
            em2rs_cmd = cur.fetchone()
            em2rs_setpoint_command = None if em2rs_cmd is None else em2rs_cmd["value"]

            em2rs_id = int((current_cfg().get("em2rs_556") or {}).get("slave_id", 31))
            cur.execute(
                "SELECT * FROM em2rs_556_state WHERE device_id = %s",
                (em2rs_id,),
            )
            em2rs_row = cur.fetchone()

            cur.execute("SELECT ts FROM em2rs_556 ORDER BY id DESC LIMIT 1")
            sample = cur.fetchone()
            em2rs_sample_ts = sample["ts"] if sample else None

    except:

        db_ok = False
        trow = {}
        irow = {}
        prow = {}
        t_last = None
        i_last = None
        gd20_row = None
        gd20_setpoint_command = None
        em2rs_setpoint_command = None
        em2rs_row = None
        em2rs_sample_ts = None

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
        "em2rs": _em2rs_with_gd20(
            em2rs_payload(em2rs_row, em2rs_sample_ts, em2rs_setpoint_command),
            gd20_row,
        ),
    }


def _em2rs_with_gd20(payload, gd20_row):

    if payload is None:
        return None

    gd20_cfg = current_cfg().get("invt_gd20") or {}
    em2rs_cfg = current_cfg().get("em2rs_556") or {}
    trim = ((em2rs_cfg.get("valve") or {}).get("p7_trim") or {})
    max_age_s = ((gd20_cfg.get("stability") or {}).get("max_age_s", 10))
    updated = None if gd20_row is None else gd20_row.get("updated_ts")
    stable, error = gd20_stability(
        None if gd20_row is None else gd20_row.get("pid_setpoint_kpa"),
        None if gd20_row is None else gd20_row.get("pid_feedback_kpa"),
        trim.get("invt_tolerance_kpa"),
        None if gd20_row is None else gd20_row.get("running"),
        None if gd20_row is None else gd20_row.get("online"),
        gd20_sample_age_s(updated, datetime.now()),
        max_age_s,
    )
    payload["gd20_stable"] = 1 if stable else 0
    payload["gd20_error_kpa"] = error
    payload["gd20_running"] = _gd20_running_flag(gd20_row, gd20_cfg, max_age_s)

    return payload


def _gd20_running_flag(row, gd20_cfg, max_age_s):

    if row is None or not row.get("online"):
        return None

    age = gd20_sample_age_s(row.get("updated_ts"), datetime.now())
    fresh = age is not None and max_age_s is not None and age <= float(max_age_s)

    if not fresh:
        return None

    running_values = (
        ((gd20_cfg.get("monitoring") or {}).get("status_word") or {}).get("running_values")
        or (1, 2)
    )
    known = gd20_is_running(row.get("status_code"), running_values)

    if known is None:
        return None

    return 1 if known else 0


def _num(value):

    if value is None:
        return None

    return float(value)


def gd20_payload(row, setpoint_command=None):

    if not row:
        return None

    updated = row.get("updated_ts")
    cfg = current_cfg()
    monitoring = (cfg.get("invt_gd20") or {}).get("monitoring") or {}
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
        "visible": gd20_row_visible(cfg),
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


def _p7_setpoint_limits():

    channel = (
        (current_cfg().get("conversion") or {})
        .get("channels", {})
        .get("p7")
        or {}
    )

    return float(channel.get("a", 0)), float(channel.get("b", 220))


def em2rs_payload(row, sample_ts=None, setpoint_command=None):

    if not row:
        return None

    full = int(
        ((current_cfg().get("em2rs_556") or {}).get("valve") or {}).get("full_travel_steps") or 0
    )
    actual = row.get("actual_position_steps")
    updated = row.get("updated_ts")
    actual_pct = None if actual is None or not full else actual * 100.0 / full

    return {
        "device_id": int(row["device_id"]),
        "online": int(row["online"]),
        "mode": row.get("mode") or "MANUAL",
        "setpoint_command_kpa": _num(setpoint_command),
        "requested_position_pct": _num(row.get("requested_position_pct")),
        "requested_position_steps": None if row.get("requested_position_steps") is None else int(row["requested_position_steps"]),
        "actual_position_steps": None if actual is None else int(actual),
        "actual_position_pct": actual_pct,
        "expected_delta_steps": None if row.get("expected_delta_steps") is None else int(row["expected_delta_steps"]),
        "actual_delta_steps": None if row.get("actual_delta_steps") is None else int(row["actual_delta_steps"]),
        "position_check": row.get("position_check"),
        "running": int(row.get("running") or 0),
        "alarm": int(row.get("alarm") or 0),
        "alarm_text": row.get("alarm_text"),
        "motion_phase": row.get("motion_phase"),
        "trim_settle_remaining_s": (
            settle_remaining_s(row.get("trim_settle_deadline"), time.time())
            if row.get("motion_phase") == "TRIM_SETTLE"
            else None
        ),
        "position_valid": int(row.get("position_valid") or 0),
        "updated_ts": updated.strftime("%Y-%m-%d %H:%M:%S") if updated else None,
        "sample_ts": sample_ts.strftime("%Y-%m-%d %H:%M:%S") if sample_ts else None,
    }


def _store_control(parameter, value):

    conn = None

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO control (parameter, value, source)
                VALUES (%s, %s, 'hmi')
                """,
                (parameter, value),
            )
            cur.execute(
                """
                REPLACE INTO control_state (parameter, value, source)
                VALUES (%s, %s, 'hmi')
                """,
                (parameter, value),
            )

    except Exception as e:

        raise HTTPException(status_code=500, detail="command was not stored") from e

    finally:

        if conn:
            conn.close()


def _em2rs_blocks_motion():

    cfg = current_cfg().get("em2rs_556") or {}
    device_id = int(cfg.get("slave_id", 31))
    conn = None

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT mode, running, alarm
                FROM em2rs_556_state
                WHERE device_id = %s
                """,
                (device_id,),
            )
            row = cur.fetchone()

    finally:

        if conn:
            conn.close()

    if not row:
        return None

    if int(row.get("running") or 0):
        return "driver beží"

    if int(row.get("alarm") or 0):
        return "alarm"

    if str(row.get("mode") or "MANUAL").upper() == "AUTO":
        return "režim Auto"

    return None


@app.get("/em2rs", response_class=HTMLResponse)
def em2rs_page(request: Request):

    setpoint_min, setpoint_max = _p7_setpoint_limits()

    return templates.TemplateResponse(
        "em2rs.html",
        {
            "request": request,
            "refresh_ms": _refresh_ms,
            "setpoint_min": setpoint_min,
            "setpoint_max": setpoint_max,
            "setpoint_min_label": format(setpoint_min, "g"),
            "setpoint_max_label": format(setpoint_max, "g"),
        },
    )


@app.post("/api/em2rs/mode")
async def em2rs_mode(request: Request):

    body = await request.json()
    mode = str(body.get("mode", "")).strip().upper()

    if mode not in ("MANUAL", "AUTO"):
        raise HTTPException(status_code=400, detail="mode must be MANUAL or AUTO")

    _store_control("em2rs_mode", mode)

    return {"status": "ok", "mode": mode}


@app.post("/api/em2rs/setpoint")
async def em2rs_setpoint(request: Request):

    body = await request.json()
    setpoint = body.get("setpoint_kpa")

    if isinstance(setpoint, bool) or not isinstance(setpoint, (int, float)):
        raise HTTPException(status_code=400, detail="setpoint_kpa must be a number")

    setpoint = float(setpoint)

    if not math.isfinite(setpoint):
        raise HTTPException(status_code=400, detail="setpoint_kpa must be a number")

    low, high = _p7_setpoint_limits()

    if setpoint < low or setpoint > high:
        raise HTTPException(
            status_code=400,
            detail=f"setpoint_kpa must be {low:g}..{high:g}",
        )

    value = format(setpoint, "f").rstrip("0").rstrip(".") or "0"
    _store_control("em2rs_p7_setpoint_kpa", value)

    return {"status": "ok", "setpoint_kpa": setpoint}


@app.post("/api/em2rs/homing")
async def em2rs_homing():

    reason = _em2rs_blocks_motion()

    if reason:
        raise HTTPException(status_code=409, detail=reason)

    _store_control("em2rs_homing", str(time.time_ns()))

    return {"status": "ok"}


@app.post("/api/em2rs/position")
async def em2rs_position(request: Request):

    body = await request.json()
    percent = body.get("position_pct")

    if isinstance(percent, bool) or not isinstance(percent, (int, float)):
        raise HTTPException(status_code=400, detail="position_pct must be a number")

    percent = float(percent)

    if not math.isfinite(percent) or percent < 0 or percent > 100:
        raise HTTPException(status_code=400, detail="position_pct must be 0..100")

    reason = _em2rs_blocks_motion()

    if reason:
        raise HTTPException(status_code=409, detail=reason)

    value = format(percent, "f").rstrip("0").rstrip(".") or "0"
    _store_control("em2rs_position_pct", value)

    return {"status": "ok", "position_pct": percent}


@app.post("/api/em2rs/alarm-reset")
async def em2rs_alarm_reset():

    _store_control("em2rs_alarm_reset", str(time.time_ns()))

    return {"status": "ok"}


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