"""Dávkový prepis histórie z RAM MariaDB na SD kartu.

Nové riadky sa kopírujú raz za interval, jedna transakcia na dávku.
Watermark je MAX(id) už uložené na karte, takže existujúca história sa
nekopíruje znova. Stavové tabuľky idú až keď je archive_sync.sync_state true.
"""

import subprocess
import sys
import time

import pymysql
from pymysql.cursors import DictCursor

from iot_core.core.config import load_config


HISTORY_TABLES = (
    "temperature",
    "current_loop",
    "conversion_table",
    "invt_gd20",
    "em2rs_556",
    "relay",
    "relay_history",
    "relay_cycles",
    "control",
    "system",
    "fault_log",
)

STATE_TABLES = (
    "control_state",
    "relay_state",
    "invt_gd20_state",
    "em2rs_556_state",
    "system_info",
)

PURGE_KEY = "__purge_archive"


def ident(name):

    if not name.replace("_", "").isalnum():
        raise ValueError(f"neplatný názov tabuľky: {name}")

    return f"`{name}`"


def connect(cfg):

    return pymysql.connect(
        host=cfg["host"],
        port=int(cfg["port"]),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["name"],
        autocommit=False,
        charset="utf8mb4",
        cursorclass=DictCursor,
        connect_timeout=5,
        read_timeout=120,
        write_timeout=120,
    )


def max_id(conn, table):

    with conn.cursor() as cur:
        cur.execute(f"SELECT COALESCE(MAX(id), 0) AS max_id FROM {ident(table)}")
        return int(cur.fetchone()["max_id"])


def align_autoincrement(hot, archive):

    # ALTER TABLE commituje sám. Číslo ide za najvyššie existujúce id.
    # Dump schémy má staré AUTO_INCREMENT, to by po reboote spravilo dieru.
    for table in HISTORY_TABLES:
        target = max(max_id(hot, table), max_id(archive, table)) + 1

        with hot.cursor() as cur:
            cur.execute(
                f"ALTER TABLE {ident(table)} AUTO_INCREMENT = {target}"
            )

    hot.commit()
    archive.commit()


def ensure_state_table(archive):

    with archive.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS archive_sync_state (
                table_name varchar(64) NOT NULL,
                last_id bigint(20) unsigned NOT NULL,
                updated_ts timestamp NOT NULL
                    DEFAULT current_timestamp()
                    ON UPDATE current_timestamp(),
                PRIMARY KEY (table_name)
            ) ENGINE=InnoDB
            """
        )


def watermark(archive, table):

    with archive.cursor() as cur:
        cur.execute(
            "SELECT last_id FROM archive_sync_state WHERE table_name = %s",
            (table,),
        )
        row = cur.fetchone()

        if row:
            return int(row["last_id"])

        last_id = max_id(archive, table)
        cur.execute(
            "INSERT INTO archive_sync_state (table_name, last_id) VALUES (%s, %s)",
            (table, last_id),
        )
        return last_id


def save_watermark(archive, table, last_id):

    with archive.cursor() as cur:
        cur.execute(
            """
            INSERT INTO archive_sync_state (table_name, last_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE last_id = VALUES(last_id)
            """,
            (table, last_id),
        )


_skipped_columns = set()


def table_columns(conn, table):

    with conn.cursor() as cur:
        cur.execute(f"SHOW COLUMNS FROM {ident(table)}")
        return [row["Field"] for row in cur.fetchall()]


def write_rows(archive, table, rows, upsert, ignore_duplicates=False):

    allowed = set(table_columns(archive, table))
    cols = [col for col in rows[0].keys() if col in allowed]
    skipped = tuple(col for col in rows[0].keys() if col not in allowed)

    if not cols:
        raise RuntimeError(f"{table}: cieľová tabuľka nemá spoločný stĺpec")

    if skipped and (table, skipped) not in _skipped_columns:
        _skipped_columns.add((table, skipped))
        print(
            f"archive sync: {table} preskakuje stĺpce {', '.join(skipped)}",
            flush=True,
        )

    rows = [{col: row[col] for col in cols} for row in rows]
    colsql = ", ".join(ident(col) for col in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    values = [tuple(row[col] for col in cols) for row in rows]
    verb = "INSERT IGNORE" if ignore_duplicates else "INSERT"
    sql = f"{verb} INTO {ident(table)} ({colsql}) VALUES ({placeholders})"

    if upsert:
        updates = ", ".join(
            f"{ident(col)} = VALUES({ident(col)})"
            for col in cols
            if col != "id"
        )
        sql += f" ON DUPLICATE KEY UPDATE {updates}"

    with archive.cursor() as cur:
        cur.executemany(sql, values)


def copy_history(hot, archive, table, batch_rows):

    last_id = watermark(archive, table)
    start_id = last_id
    copied = 0

    while True:
        with hot.cursor() as cur:
            cur.execute(
                f"""
                SELECT * FROM {ident(table)}
                WHERE id > %s
                ORDER BY id
                LIMIT %s
                """,
                (last_id, batch_rows),
            )
            rows = cur.fetchall()

        if not rows:
            break

        write_rows(
            archive,
            table,
            rows,
            upsert=(table == "fault_log"),
            ignore_duplicates=(table != "fault_log"),
        )
        last_id = int(rows[-1]["id"])
        copied += len(rows)

        if len(rows) < batch_rows:
            break

    if table == "fault_log":
        with hot.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {ident(table)} WHERE active = 1 AND id <= %s",
                (last_id,),
            )
            active = cur.fetchall()

        if active:
            write_rows(archive, table, active, upsert=True)

    if last_id != start_id:
        save_watermark(archive, table, last_id)

    return copied


def copy_state(hot, archive, table):

    with hot.cursor() as cur:
        cur.execute(f"SELECT * FROM {ident(table)}")
        rows = cur.fetchall()

    if not rows:
        return 0

    write_rows(archive, table, rows, upsert=True)
    return len(rows)


def purge_hot(hot, hours, watermarks):

    if hours <= 0:
        return

    with hot.cursor() as cur:
        for table, last_id in watermarks.items():
            cur.execute(
                f"""
                DELETE FROM {ident(table)}
                WHERE ts < (NOW() - INTERVAL %s HOUR)
                  AND id <= %s
                """,
                (int(hours), last_id),
            )


def purge_archive(archive, days):

    if days <= 0:
        return

    with archive.cursor() as cur:
        cur.execute(
            "SELECT updated_ts FROM archive_sync_state WHERE table_name = %s",
            (PURGE_KEY,),
        )
        row = cur.fetchone()

        if row is not None:
            cur.execute(
                """
                SELECT updated_ts >= (NOW() - INTERVAL 1 DAY) AS recent
                FROM archive_sync_state
                WHERE table_name = %s
                """,
                (PURGE_KEY,),
            )
            if int(cur.fetchone()["recent"]):
                return

        for table in HISTORY_TABLES:
            cur.execute(
                f"""
                DELETE FROM {ident(table)}
                WHERE ts < (NOW() - INTERVAL %s DAY)
                """,
                (int(days),),
            )

        cur.execute(
            """
            INSERT INTO archive_sync_state (table_name, last_id, updated_ts)
            VALUES (%s, 0, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                last_id = 0,
                updated_ts = CURRENT_TIMESTAMP
            """,
            (PURGE_KEY,),
        )


def run_once(cfg):

    sync_cfg = cfg["archive_sync"]
    hot = connect(cfg["database_hot"])
    archive = connect(cfg["database_archive"])
    copied = {}

    try:
        align_autoincrement(hot, archive)
        ensure_state_table(archive)
        watermarks = {}

        for table in HISTORY_TABLES:
            copied[table] = copy_history(
                hot,
                archive,
                table,
                int(sync_cfg.get("batch_rows", 5000)),
            )
            watermarks[table] = watermark(archive, table)

        if sync_cfg.get("sync_state"):
            for table in STATE_TABLES:
                copied[table] = copy_state(hot, archive, table)

        purge_hot(hot, float(sync_cfg.get("hot_retention_hours", 24)), watermarks)

        if sync_cfg.get("purge_archive"):
            purge_archive(archive, int(sync_cfg.get("archive_retention_days", 90)))

        archive.commit()
        hot.commit()
        return copied

    except Exception:
        archive.rollback()
        hot.rollback()
        raise

    finally:
        hot.close()
        archive.close()


def unit_running(name):

    result = subprocess.run(
        ["systemctl", "show", "-p", "MainPID", "--value", name],
        capture_output=True,
        text=True,
    )
    pid = result.stdout.strip()
    return pid.isdigit() and int(pid) > 0


def assert_writers_stopped():

    # MainPID, nie ActiveState. Pri štarte master čaká na tento backfill
    # a je v stave activating, hoci proces ešte nebeží.
    busy = [
        name
        for name in ("iot-master", "iot-dashboard", "iot-db-archive")
        if unit_running(name)
    ]

    if busy:
        raise RuntimeError(
            "backfill by zmazal dáta v RAM, kým beží: " + ", ".join(busy)
        )


def copy_window(archive, hot, table, hours, batch_rows, or_sql=None):

    predicate = "ts >= (NOW() - INTERVAL %s HOUR)"

    if or_sql:
        predicate = f"({predicate} OR {or_sql})"

    last_id = 0
    copied = 0

    while True:
        with archive.cursor() as cur:
            cur.execute(
                f"""
                SELECT * FROM {ident(table)}
                WHERE {predicate} AND id > %s
                ORDER BY id
                LIMIT %s
                """,
                (int(hours), last_id, batch_rows),
            )
            rows = cur.fetchall()

        if not rows:
            break

        write_rows(hot, table, rows, upsert=True)
        last_id = int(rows[-1]["id"])
        copied += len(rows)

        if len(rows) < batch_rows:
            break

    return copied


def backfill_hot(cfg):

    """Posledných 24 h histórie a celý stav z karty do prázdnej RAM."""

    assert_writers_stopped()
    sync_cfg = cfg["archive_sync"]
    hours = int(sync_cfg.get("hot_retention_hours", 24))
    batch_rows = int(sync_cfg.get("batch_rows", 5000))
    hot = connect(cfg["database_hot"])
    archive = connect(cfg["database_archive"])
    started = time.monotonic()

    try:
        with hot.cursor() as cur:
            for table in HISTORY_TABLES + STATE_TABLES:
                cur.execute(f"DELETE FROM {ident(table)}")
        hot.commit()

        copied = {}

        for table in HISTORY_TABLES:
            or_sql = "active = 1" if table == "fault_log" else None
            copied[table] = copy_window(
                archive, hot, table, hours, batch_rows, or_sql
            )
            hot.commit()

        for table in STATE_TABLES:
            with archive.cursor() as cur:
                cur.execute(f"SELECT * FROM {ident(table)}")
                rows = cur.fetchall()

            if rows:
                write_rows(hot, table, rows, upsert=True)

            copied[table] = len(rows)
        hot.commit()

        ensure_state_table(archive)

        for table in HISTORY_TABLES:
            save_watermark(archive, table, max_id(archive, table))

        archive.commit()
        align_autoincrement(hot, archive)

        detail = ", ".join(f"{table} {count}" for table, count in copied.items())
        print(
            f"backfill hot: {detail} ({time.monotonic() - started:.2f}s)",
            flush=True,
        )

    except Exception:
        hot.rollback()
        archive.rollback()
        raise

    finally:
        hot.close()
        archive.close()


def run_probe(cfg):

    """Jeden riadok cez pomocnú tabuľku. Živé tabuľky sa nemenia."""

    ddl = """
        CREATE TABLE _sync_probe (
            id bigint(20) unsigned NOT NULL,
            ts timestamp NOT NULL,
            note varchar(32) NOT NULL,
            PRIMARY KEY (id)
        ) ENGINE=InnoDB
    """
    hot = connect(cfg["database_hot"])
    archive = connect(cfg["database_archive"])

    try:
        for conn in (hot, archive):
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS _sync_probe")
                cur.execute(ddl)
            conn.commit()

        with hot.cursor() as cur:
            cur.execute(
                "INSERT INTO _sync_probe (id, ts, note) VALUES (1, NOW(), 'probe')"
            )
            cur.execute("SELECT * FROM _sync_probe")
            rows = cur.fetchall()
        hot.commit()

        write_rows(archive, "_sync_probe", rows, upsert=False)
        archive.commit()

        with archive.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM _sync_probe WHERE id = 1 AND note = 'probe'"
            )
            found = int(cur.fetchone()["n"])

        if found != 1:
            raise RuntimeError("probe sa na kartu neuložila")

        print("archive sync probe: ok", flush=True)

    finally:
        for conn in (hot, archive):
            try:
                with conn.cursor() as cur:
                    cur.execute("DROP TABLE IF EXISTS _sync_probe")
                conn.commit()
            finally:
                conn.close()


def format_summary(copied, elapsed):

    parts = [f"{table} +{count}" for table, count in copied.items() if count]
    detail = ", ".join(parts) if parts else "nič nové"
    return f"archive sync: {detail} ({elapsed:.2f}s)"


def main():

    once = "--once" in sys.argv

    if "--probe" in sys.argv:
        try:
            run_probe(load_config())
        except Exception as exc:
            print(f"archive sync probe error: {exc}", flush=True)
            return 1
        return 0

    if "--backfill" in sys.argv:
        try:
            backfill_hot(load_config())
        except Exception as exc:
            print(f"backfill error: {exc}", flush=True)
            return 1
        return 0

    while True:
        started = time.monotonic()
        cfg = load_config()
        interval = float(cfg["archive_sync"].get("interval_s", 200))

        try:
            copied = run_once(cfg)
            print(format_summary(copied, time.monotonic() - started), flush=True)
            failed = False

        except Exception as exc:
            print(f"archive sync error: {exc}", flush=True)
            failed = True

        if once:
            return 1 if failed else 0

        remaining = interval - (time.monotonic() - started)
        time.sleep(max(1.0, remaining))


if __name__ == "__main__":
    sys.exit(main())
