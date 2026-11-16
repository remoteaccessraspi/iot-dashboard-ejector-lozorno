import asyncio
import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode

from iot_core.core.config import load_config, load_openai_admin_key

ROOT = Path(__file__).resolve().parents[2]
API = "https://api.openai.com/v1/organization/costs"
QUANT = Decimal("0.000001")
WINDOW_DAYS = 31
PAGE_CAP = 20
ATTEMPTS = 4


class BillingError(Exception):

    def __init__(self, code):

        self.code = code
        super().__init__(code)


class _NoRedirect(urllib.request.HTTPRedirectHandler):

    def redirect_request(self, req, fp, code, msg, headers, newurl):

        return None


def settings(cfg):

    block = (cfg or {}).get("openai_billing") or {}

    try:
        interval = int(block.get("poll_interval_seconds") or 600)
    except (TypeError, ValueError):
        interval = 600

    return {
        "enabled": bool(block.get("enabled", False)),
        "project_id": str(block.get("project_id") or "").strip(),
        "poll_interval_seconds": max(60, interval),
        "tracking_start_utc": str(block.get("tracking_start_utc") or "2026-11-01T00:00:00Z"),
        "currency": str(block.get("currency") or "USD").upper(),
    }


def project_ready(project_id):

    return project_id.startswith("proj_") and "REPLACE" not in project_id and not project_id.startswith("sk-")


def _cache_path(var_dir):

    return Path(var_dir or ROOT / "var") / "openai-costs.json"


def load_cache(var_dir=None):

    try:
        raw = json.loads(_cache_path(var_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}

    if not isinstance(raw, dict):
        raw = {}

    days = raw.get("days") if isinstance(raw.get("days"), dict) else {}

    return {
        "days": {str(day): str(amount) for day, amount in days.items()},
        "last_successful_update_utc": raw.get("last_successful_update_utc"),
        "last_error": str(raw.get("last_error") or ""),
    }


def save_cache(cache, var_dir=None):

    path = _cache_path(var_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "days": cache.get("days") or {},
        "last_successful_update_utc": cache.get("last_successful_update_utc"),
        "last_error": cache.get("last_error") or "",
    }
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, path)


def _money(value):

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BillingError("bad_amount") from None


def _fmt(amount):

    return format(amount.quantize(QUANT), "f")


def _parse_start(text):

    try:
        parsed = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        raise BillingError("bad_config") from None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _stamp(moment):

    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day(moment):

    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d")


def windows(start_unix, end_unix):

    step = WINDOW_DAYS * 86400
    cursor = start_unix

    while cursor < end_unix:
        nxt = min(end_unix, cursor + step)
        yield cursor, nxt
        cursor = nxt


def costs_url(start_unix, end_unix, page=None):

    query = {
        "start_time": int(start_unix),
        "end_time": int(end_unix),
        "bucket_width": "1d",
        "group_by": "project_id",
        "limit": WINDOW_DAYS,
    }

    if page:
        query["page"] = page

    return API + "?" + urlencode(query)


def apply_buckets(days, buckets, project_id):

    for bucket in buckets or []:
        if not isinstance(bucket, dict) or "results" not in bucket or "start_time" not in bucket:
            continue

        total = Decimal("0")

        for row in bucket.get("results") or []:
            if not isinstance(row, dict) or row.get("project_id") != project_id:
                continue

            amount = row.get("amount") or {}
            currency = str(amount.get("currency") or "usd").upper()

            if currency != "USD" or amount.get("value") is None:
                continue

            total += _money(amount.get("value"))

        day = _day(datetime.fromtimestamp(int(bucket["start_time"]), timezone.utc))
        days[day] = total

    return days


def _retry_after(value, fallback):

    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return fallback

    return min(max(seconds, 0), 60)


def http_get(url, key, timeout=20):

    request = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())

    try:
        with opener.open(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"), parse_float=str)
            return response.status, payload, {}
    except urllib.error.HTTPError as error:
        retry_after = error.headers.get("Retry-After") if error.headers else None
        return error.code, None, {"retry_after": retry_after}
    except (TimeoutError, socket.timeout):
        raise BillingError("timeout") from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise BillingError("timeout") from None
        raise BillingError("network") from None


def fetch_page(url, key, get, sleep):

    delay = 1.0
    last = "network"

    for attempt in range(ATTEMPTS):
        try:
            status, body, meta = get(url, key)
        except BillingError as error:
            last = error.code
            status, body, meta = None, None, {}

        if status == 200 and isinstance(body, dict):
            return body

        if status in (401, 403):
            raise BillingError("unauthorized")

        if status == 429:
            last = "rate_limit"
            wait = _retry_after(meta.get("retry_after"), delay)
        elif status is not None and status >= 500:
            last = "server"
            wait = delay
        elif status is None:
            wait = delay
        else:
            raise BillingError("http_" + str(status))

        if attempt == ATTEMPTS - 1:
            break

        sleep(wait)
        delay = min(delay * 2, 30)

    raise BillingError(last)


def fetch_days(start, end, project_id, key, get, sleep):

    days = {}

    for window_start, window_end in windows(int(start.timestamp()), int(end.timestamp())):
        page = None
        seen = set()

        for _ in range(PAGE_CAP):
            body = fetch_page(costs_url(window_start, window_end, page), key, get, sleep)
            apply_buckets(days, body.get("data"), project_id)

            if not body.get("has_more"):
                break

            page = body.get("next_page")

            if not page or page in seen:
                break

            seen.add(page)

    return days


def _totals(days, now, tracking_start):

    today = _day(now)
    month = today[:7]
    start_day = _day(tracking_start)
    today_sum = month_sum = total = Decimal("0")

    for day, amount in days.items():
        if day < start_day:
            continue

        total += amount

        if day == today:
            today_sum += amount

        if day[:7] == month:
            month_sum += amount

    return today_sum, month_sum, total


def view(cfg, var_dir=None, now=None):

    opts = settings(cfg)
    cache = load_cache(var_dir)
    now = now or datetime.now(timezone.utc)
    days = {}

    for day, amount in cache["days"].items():
        try:
            days[day] = _money(amount)
        except BillingError:
            continue

    try:
        tracking_start = _parse_start(opts["tracking_start_utc"])
        today_sum, month_sum, total = _totals(days, now, tracking_start)
    except BillingError:
        today_sum = month_sum = total = Decimal("0")
        status = "bad_config"
    else:
        status = _status(opts, cache)

    stale = status != "ok"

    return {
        "project_id": opts["project_id"],
        "currency": opts["currency"],
        "today_usd": _fmt(today_sum),
        "month_usd": _fmt(month_sum),
        "total_since_tracking_start_usd": _fmt(total),
        "tracking_start_utc": opts["tracking_start_utc"],
        "last_successful_update_utc": cache.get("last_successful_update_utc"),
        "stale": stale,
        "status": status,
    }


def _status(opts, cache):

    if not opts["enabled"]:
        return "disabled"

    if not load_openai_admin_key():
        return "missing_key"

    if not project_ready(opts["project_id"]):
        return "missing_project"

    if cache.get("last_error"):
        return cache["last_error"]

    if not cache.get("last_successful_update_utc"):
        return "not_initialized"

    return "ok"


def _remember(code, var_dir):

    cache = load_cache(var_dir)
    cache["last_error"] = code
    save_cache(cache, var_dir)


def refresh(cfg, get=http_get, sleep=None, now=None, var_dir=None, key=None):

    opts = settings(cfg)
    now = now or datetime.now(timezone.utc)
    sleep = sleep or time.sleep

    if not opts["enabled"]:
        return view(cfg, var_dir, now)

    key = load_openai_admin_key() if key is None else key

    if not key or not project_ready(opts["project_id"]):
        return view(cfg, var_dir, now)

    try:
        tracking_start = _parse_start(opts["tracking_start_utc"])
    except BillingError as error:
        _remember(error.code, var_dir)
        return view(cfg, var_dir, now)

    end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)

    if tracking_start >= end:
        cache = load_cache(var_dir)
        cache["last_successful_update_utc"] = _stamp(now)
        cache["last_error"] = ""
        save_cache(cache, var_dir)
        return view(cfg, var_dir, now)

    try:
        fetched = fetch_days(tracking_start, end, opts["project_id"], key, get, sleep)
    except BillingError as error:
        _remember(error.code, var_dir)
        return view(cfg, var_dir, now)

    cache = load_cache(var_dir)

    for day, amount in fetched.items():
        if day >= _day(tracking_start):
            cache["days"][day] = _fmt(amount)

    cache["last_successful_update_utc"] = _stamp(now)
    cache["last_error"] = ""
    save_cache(cache, var_dir)
    return view(cfg, var_dir, now)


async def loop(stop):

    while not stop.is_set():
        try:
            cfg = load_config()
            opts = settings(cfg)

            if opts["enabled"]:
                await asyncio.to_thread(refresh, cfg)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print("openai costs:", type(error).__name__)

        try:
            cfg = load_config()
            wait = settings(cfg)["poll_interval_seconds"]
            await asyncio.wait_for(stop.wait(), wait)
            return
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            raise
