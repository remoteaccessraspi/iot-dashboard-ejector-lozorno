from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pathlib import Path
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional

import yaml
import pymysql


# --------------------------------------------------
# INIT
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "config" / "settings.yaml"

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

def load_cfg():
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))

_cfg = load_cfg()

_db_cfg = _cfg["database"]

_refresh_ms = _cfg.get("hmi", {}).get("refresh_ms", 2000)

# relay names z YAML
_relay_names = _cfg.get("relay", {}).get("names", {})


# --------------------------------------------------
# DB CONNECT
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


# --------------------------------------------------
# CONTROL MODEL
# --------------------------------------------------

class ControlParams(BaseModel):

    pwm_period: Optional[float] = None
    pwm_duty: Optional[float] = None

    pid_t_set: Optional[float] = None
    pid_t_full: Optional[float] = None
    pid_t_move: Optional[float] = None


# --------------------------------------------------
# CHANNEL UTIL
# --------------------------------------------------

def build_channel_cfg(prefix):

    channels = _cfg.get("channels", {})

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
# DB TABLE -> DICT
# --------------------------------------------------

def read_table_dict(cur, table, key_col, val_cols):

    try:

        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()

        out = {}

        for r in rows:

            key = r[key_col]

            if len(val_cols) == 1:
                out[key] = r[val_cols[0]]
            else:
                out[key] = {c: r[c] for c in val_cols}

        return out

    except:
        return {}


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


@app.get("/control", response_class=HTMLResponse)
def control_page(request: Request):

    return templates.TemplateResponse(
        "control.html",
        {
            "request": request,
            "pwm": _cfg.get("pwm", {}),
            "pid": _cfg.get("pid", {})
        }
    )


@app.get("/relay", response_class=HTMLResponse)
def relay_page(request: Request):

    return templates.TemplateResponse(
        "relay.html",
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

    return templates.TemplateResponse(
        "graph.html",
        {
            "request": request,
            "t_names": t_names,
            "t_units": t_units,
            "p_names": p_names,
            "p_units": p_units
        }
    )


# --------------------------------------------------
# API MONITOR
# --------------------------------------------------

@app.get("/api/latest")
def api_latest():

    db_ok = True
    conn = None

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

            relay = read_table_dict(
                cur,
                "relay_state",
                "name",
                ["state", "source"]
            )

            control = read_table_dict(
                cur,
                "control_state",
                "parameter",
                ["value", "source"]
            )

    except:

        db_ok = False
        trow = {}
        irow = {}
        prow = {}
        relay = {}
        control = {}
        t_last = None
        i_last = None

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

        "relay_state": relay,
        "relay_names": _relay_names,

        "control_state": control,

        "t_last_db": t_last.strftime("%Y-%m-%d %H:%M:%S") if t_last else None,
        "i_last_db": i_last.strftime("%Y-%m-%d %H:%M:%S") if i_last else None,
    }


# --------------------------------------------------
# GRAPH SQL
# --------------------------------------------------

SQL_JOIN = """
SELECT
    t.ts,
    t.t1,t.t2,t.t3,t.t4,t.t5,t.t6,t.t7,t.t8,
    p.p1,p.p2,p.p3,p.p4,p.p5,p.p6,p.p7,p.p8
FROM temperature t
LEFT JOIN conversion_table p
ON p.ts = t.ts
WHERE t.ts >= %s
ORDER BY t.ts
"""


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

            cur.execute(SQL_JOIN, (start,))
            rows = cur.fetchall()

        MAX_POINTS = 500

        if len(rows) > MAX_POINTS:
            step = len(rows) // MAX_POINTS
            rows = rows[::step]

        data = {
            "time": [],
            "t": {f"t{i}": [] for i in range(1, 9)},
            "p": {f"p{i}": [] for i in range(1, 9)}
        }

        for r in rows:

            ts = r.get("ts")

            data["time"].append(ts.strftime("%H:%M:%S") if ts else None)

            for i in range(1, 9):

                tv = r.get(f"t{i}")
                pv = r.get(f"p{i}")

                data["t"][f"t{i}"].append(None if tv is None else float(tv))
                data["p"][f"p{i}"].append(None if pv is None else float(pv))

        return data

    finally:

        if conn:
            conn.close()


# --------------------------------------------------
# LIVE GRAPH
# --------------------------------------------------

@app.get("/api/live")
def api_live(minutes: int = 10):

    start = datetime.now() - timedelta(minutes=minutes)

    conn = None

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            cur.execute(SQL_JOIN, (start,))
            rows = cur.fetchall()

        result = {
            "time": [],
            "t": {f"t{i}": [] for i in range(1, 9)},
            "p": {f"p{i}": [] for i in range(1, 9)}
        }

        for r in rows:

            ts = r.get("ts")

            result["time"].append(ts.strftime("%H:%M:%S") if ts else None)

            for i in range(1, 9):

                tv = r.get(f"t{i}")
                pv = r.get(f"p{i}")

                result["t"][f"t{i}"].append(None if tv is None else float(tv))
                result["p"][f"p{i}"].append(None if pv is None else float(pv))

        return result

    finally:

        if conn:
            conn.close()


# --------------------------------------------------
# CONTROL SAVE API
# --------------------------------------------------

@app.post("/api/control/save_all")
async def api_control_save_all(data: ControlParams):

    conn = None

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            ts = datetime.now()

            for param, value in data.dict().items():

                if value is None:
                    continue

                cur.execute(
                    """
                    INSERT INTO control(parameter,value,ts)
                    VALUES (%s,%s,%s)
                    """,
                    (param, value, ts)
                )

                cur.execute(
                    """
                    REPLACE INTO control_state(parameter,value,source)
                    VALUES (%s,%s,'hmi')
                    """,
                    (param, value)
                )

        return {"status": "ok"}

    except Exception as e:

        print("CONTROL SAVE ERROR:", e)

        return {"status": "error", "detail": str(e)}

    finally:

        if conn:
            conn.close()
# --------------------------------------------------
# RELAY SET API
# --------------------------------------------------

@app.post("/api/relay/set")
async def api_relay_set(data: dict):

    name = data.get("name")
    state = int(data.get("state", 0))

    conn = None

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            cur.execute("""
                REPLACE INTO relay_state(name,state,source)
                VALUES (%s,%s,'hmi')
            """, (name, state))

        return {"status": "ok"}

    except Exception as e:

        print("RELAY SET ERROR:", e)

        return {
            "status": "error",
            "detail": str(e)
        }

    finally:

        if conn:
            conn.close()