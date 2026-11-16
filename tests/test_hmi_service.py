import asyncio
import json
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import app as dashboard
from iot_core import ready as dashboard_ready
from iot_core.core.config import (
    SECRETS_PATH,
    load_config,
    load_hmi_secrets,
    load_openai_secrets,
)
from iot_core.hmi.session import (
    idle_seconds,
    password_matches,
    read_session,
    session_secret,
    sign_session,
)
from iot_core.service_mode import service_is_fresh


class _Jar(dict):

    def set(self, key, value):

        self[key] = value


class _Response:

    def __init__(self, status, headers, body):

        self.status_code = status
        self.headers = headers
        self.content = body
        self.text = body.decode()

    def json(self):

        return json.loads(self.content)


class _AppClient:

    def __init__(self, application):

        self.application = application
        self.cookies = _Jar()

    def close(self):

        return None

    def get(self, path, follow_redirects=False):

        return self._call("GET", path)

    def post(self, path, json=None):

        return self._call("POST", path, json)

    def _call(self, method, path, payload=None):

        body = b"" if payload is None else json.dumps(payload).encode()
        sent = False

        async def receive():

            nonlocal sent

            if sent:
                return {"type": "http.disconnect"}

            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        messages = []

        async def send(message):

            messages.append(message)

        headers = []
        cookie = "; ".join(f"{key}={value}" for key, value in self.cookies.items())

        if cookie:
            headers.append((b"cookie", cookie.encode()))

        if payload is not None:
            headers.append((b"content-type", b"application/json"))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
            "root_path": "",
            "app": self.application,
        }

        asyncio.run(self.application(scope, receive, send))

        status = 500
        response_headers = {}
        chunks = []

        for message in messages:
            if message["type"] == "http.response.start":
                status = message["status"]
                for key, value in message.get("headers", []):
                    response_headers[key.decode().lower()] = value.decode()
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        set_cookie = response_headers.get("set-cookie")

        if set_cookie:
            self._store_cookie(set_cookie)

        return _Response(status, response_headers, b"".join(chunks))

    def _store_cookie(self, header):

        parts = [part.strip() for part in header.split(";")]
        name, value = parts[0].split("=", 1)
        max_age = None

        for part in parts[1:]:
            if part.lower().startswith("max-age="):
                max_age = int(part.split("=", 1)[1])

        if max_age == 0 or value == "":
            self.cookies.pop(name, None)
            return

        self.cookies[name] = value


class SessionTests(unittest.TestCase):

    def test_idle_seconds_rejects_missing_and_non_positive(self):

        self.assertEqual(idle_seconds(30), 1800)
        self.assertEqual(idle_seconds("30"), 1800)
        self.assertEqual(idle_seconds(None), 1800)
        self.assertEqual(idle_seconds(0), 1800)
        self.assertEqual(idle_seconds(-4), 1800)
        self.assertEqual(idle_seconds("nope"), 1800)

    def test_empty_password_matches_only_an_empty_field(self):

        hmi = {"service_password": ""}

        self.assertTrue(password_matches("", hmi))
        self.assertFalse(password_matches(" ", hmi))
        self.assertFalse(password_matches(None, hmi))
        self.assertFalse(password_matches("", {}) )
        self.assertFalse(password_matches("", {"service_password": None}))

    def test_configured_password_is_exact(self):

        hmi = {"service_password": "tajne"}

        self.assertTrue(password_matches("tajne", hmi))
        self.assertFalse(password_matches("", hmi))
        self.assertFalse(password_matches("tajne ", hmi))

    def test_signed_cookie_expires(self):

        now = time.time()
        token = sign_session("secret", int(now) + 30)

        self.assertEqual(read_session("secret", token, now), int(now) + 30)
        self.assertIsNone(read_session("other", token, now))
        self.assertIsNone(read_session("secret", token + "x", now))
        self.assertIsNone(read_session("secret", token, int(now) + 30))
        self.assertIsNone(read_session("secret", "nope", now))
        self.assertIsNone(read_session("", token, now))

        with self.assertRaises(ValueError):
            sign_session("", int(now) + 30)

    def test_session_secret_must_be_text(self):

        self.assertEqual(session_secret({"session_secret": "abc"}), "abc")
        self.assertIsNone(session_secret({"session_secret": ""}))
        self.assertIsNone(session_secret({}))
        self.assertIsNone(session_secret(None))


class HmiSecretTests(unittest.TestCase):

    def test_password_is_not_part_of_settings(self):

        hmi = load_config().get("hmi") or {}

        self.assertEqual(hmi.get("service_idle_min"), 30)
        self.assertNotIn("service_password", hmi)
        self.assertNotIn("session_secret", hmi)

    def test_hmi_section_is_read_from_secrets(self):

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "secrets.yaml"
            path.write_text(
                "database:\n  user: db\n  password: hidden\n"
                "hmi:\n  service_password: \"\"\n  session_secret: abc\n",
                encoding="utf-8",
            )

            with patch("iot_core.core.config.SECRETS_PATH", path):
                hmi = load_hmi_secrets()

        self.assertEqual(hmi.get("service_password"), "")
        self.assertEqual(hmi.get("session_secret"), "abc")
        self.assertNotEqual(path, SECRETS_PATH)

    def test_missing_secrets_file_returns_empty(self):

        missing = Path("/tmp/does-not-exist-hmi-secrets.yaml")

        with patch("iot_core.core.config.SECRETS_PATH", missing):
            self.assertEqual(load_hmi_secrets(), {})

    def test_openai_key_is_read_from_secrets(self):

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "secrets.yaml"
            path.write_text(
                "openai:\n  api_key: sk-test\n",
                encoding="utf-8",
            )

            with patch("iot_core.core.config.SECRETS_PATH", path):
                openai = load_openai_secrets()

        self.assertEqual(openai.get("api_key"), "sk-test")

    def test_missing_openai_section_returns_empty(self):

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "secrets.yaml"
            path.write_text("hmi:\n  service_password: \"\"\n", encoding="utf-8")

            with patch("iot_core.core.config.SECRETS_PATH", path):
                self.assertEqual(load_openai_secrets(), {})


class HmiRouteTests(unittest.TestCase):

    def setUp(self):

        self.hmi = {"service_password": "", "session_secret": "test-secret"}
        self.original = dashboard.load_hmi_secrets
        dashboard.load_hmi_secrets = lambda: self.hmi
        self.service_flag = patch.object(dashboard, "store_service_session")
        self.store = self.service_flag.start()
        self.client = _AppClient(dashboard.app)

    def tearDown(self):

        self.service_flag.stop()
        dashboard.load_hmi_secrets = self.original
        self.client.close()

    def test_home_hides_service_cards_and_graph_stays_open(self):

        home = self.client.get("/")
        graph = self.client.get("/graph")

        self.assertEqual(home.status_code, 200)
        self.assertIn("t_evap_in", home.text)
        self.assertIn("t_evap_out", home.text)
        self.assertIn('id="homeDrive"', home.text)
        self.assertIn(">RUN</button>", home.text)
        self.assertNotIn('id="homeStop"', home.text)
        self.assertIn('id="serviceOpen"', home.text)
        self.assertIn(">Graph</a>", home.text)
        self.assertNotIn('href="/gd20"', home.text)
        self.assertNotIn('href="/em2rs"', home.text)
        self.assertIn('data-show-ack="0"', home.text)

        self.assertEqual(graph.status_code, 200)
        self.assertNotIn('class="title"', graph.text)
        self.assertIn('id="warnBar"', graph.text)
        self.assertLess(graph.text.index('id="chart"'), graph.text.index('id="warnBar"'))
        self.assertIn(">Graph</a>", graph.text)
        self.assertNotIn('href="/gd20"', graph.text)
        self.assertIn('data-show-ack="0"', graph.text)

    def test_service_pages_redirect_until_login(self):

        for path in ("/ck-3083es", "/ck-7082e", "/gd20", "/em2rs"):
            response = self.client.get(path, follow_redirects=False)
            self.assertEqual(response.status_code, 302, path)
            self.assertEqual(response.headers["location"], "/", path)

        blocked = (
            ("/api/alarms/ack", {"code": "X", "source": "s", "device_id": 1}),
            ("/api/gd20/setpoint", {"setpoint_kpa": 1}),
            ("/api/em2rs/mode", {"mode": "MANUAL"}),
            ("/api/em2rs/setpoint", {"setpoint_kpa": 1}),
            ("/api/em2rs/position", {"position_pct": 1}),
        )

        for path, body in blocked:
            response = self.client.post(path, json=body)
            self.assertEqual(response.status_code, 401, path)

        self.assertEqual(self.client.post("/api/em2rs/homing").status_code, 401)
        self.assertEqual(self.client.post("/api/em2rs/alarm-reset").status_code, 401)
        self.assertEqual(
            self.client.post("/api/gd20/command", json={}).status_code,
            400,
        )

    def test_empty_password_opens_service_and_logout_closes_it(self):

        denied = self.client.post("/api/hmi/service", json={"password": "nie"})
        self.assertEqual(denied.status_code, 401)

        opened = self.client.post("/api/hmi/service", json={"password": ""})
        self.assertEqual(opened.status_code, 200)
        self.assertIn("Max-Age=1800", opened.headers["set-cookie"])

        home = self.client.get("/")
        self.assertIn('href="/gd20"', home.text)
        self.assertIn("Close service", home.text)
        self.assertIn(">RUN</button>", home.text)
        self.assertIn("home-actions-service", home.text)
        self.assertIn("home.js?v=channel-label", home.text)
        self.assertNotIn('id="serviceOpen"', home.text)
        self.assertIn('data-show-ack="1"', home.text)
        gd20 = self.client.get("/gd20", follow_redirects=False)
        self.assertEqual(gd20.status_code, 200)
        self.assertIn(">RUN in service mode</button>", gd20.text)
        self.store.assert_any_call(True)
        self.assertIn('data-show-ack="1"', self.client.get("/graph").text)

        session = self.client.get("/api/hmi/session")
        self.assertEqual(session.json(), {"service": True})
        self.assertIsNone(session.headers.get("set-cookie"))

        self.assertEqual(self.client.post("/api/hmi/logout").status_code, 200)
        self.store.assert_any_call(False)
        self.assertEqual(self.client.get("/api/hmi/session").json(), {"service": False})
        self.assertEqual(
            self.client.get("/gd20", follow_redirects=False).status_code,
            302,
        )

    def test_activity_refreshes_the_cookie_without_a_password(self):

        short = sign_session("test-secret", int(time.time()) + 30)
        self.client.cookies.set("hmi_service", short)

        response = self.client.post("/api/hmi/activity")

        self.assertEqual(response.status_code, 200)
        expiry = read_session(
            "test-secret",
            self.client.cookies.get("hmi_service"),
            time.time(),
        )
        self.assertGreater(expiry, int(time.time()) + 60)
        self.store.assert_called_with(True)

    def test_expired_cookie_is_not_service(self):

        expired = sign_session("test-secret", int(time.time()) - 1)
        self.client.cookies.set("hmi_service", expired)

        self.assertEqual(self.client.get("/api/hmi/session").json(), {"service": False})
        self.assertEqual(self.client.post("/api/hmi/activity").status_code, 401)
        self.store.assert_not_called()
        self.assertEqual(
            self.client.get("/em2rs", follow_redirects=False).status_code,
            302,
        )

    def test_missing_secret_or_password_does_not_open_service(self):

        self.hmi.pop("session_secret")
        self.assertEqual(
            self.client.post("/api/hmi/service", json={"password": ""}).status_code,
            503,
        )

        self.hmi["session_secret"] = "test-secret"
        self.hmi.pop("service_password")
        self.assertEqual(
            self.client.post("/api/hmi/service", json={"password": ""}).status_code,
            401,
        )

    def _command(self, body, external_stop=0, ready=False, blocked=True, signed=True):

        conn = _CommandConn(external_stop)

        if signed:
            self.client.cookies.set(
                "hmi_service",
                sign_session("test-secret", int(time.time()) + 60),
            )

        with patch.object(dashboard, "db_connect", return_value=conn), \
             patch.object(dashboard, "start_allowed", return_value=ready), \
             patch.object(dashboard.AlarmBook, "blocks", return_value=blocked):
            response = self.client.post("/api/gd20/command", json=body)

        return response, conn

    def test_service_run_skips_temperature_and_alarm_rules(self):

        response, conn = self._command(
            {"run": True, "service": True},
            ready=False,
            blocked=True,
        )

        self.assertEqual(response.status_code, 200)
        stored = [params for _sql, params in conn.calls if params and params[0] == "gd20_run"]
        self.assertEqual(
            stored,
            [("gd20_run", "1", "service"), ("gd20_run", "1", "service")],
        )
        self.assertTrue(any("gd20_temp_recover" in sql for sql, _params in conn.calls))

    def test_main_run_keeps_the_temperature_rule_during_service(self):

        response, conn = self._command({"run": True}, ready=False, blocked=False)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "temperatures are not ready")
        self.assertFalse(any(params and params[0] == "gd20_run" for _sql, params in conn.calls))

    def test_service_run_requires_the_service_session(self):

        response, _conn = self._command({"run": True, "service": True}, signed=False)

        self.assertEqual(response.status_code, 401)

    def test_service_run_stays_blocked_by_the_external_switch(self):

        response, conn = self._command({"run": True, "service": True}, external_stop=1)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "external stop is active")
        self.assertFalse(any(params and params[0] == "gd20_run" for _sql, params in conn.calls))


class _CommandCursor:

    def __init__(self, conn):

        self.conn = conn
        self.sql = ""

    def __enter__(self):

        return self

    def __exit__(self, exc_type, exc, tb):

        return False

    def execute(self, sql, params=None):

        self.sql = sql
        self.conn.calls.append((sql, params))

    def fetchone(self):

        if "external_stop" in self.sql:
            return {"external_stop": self.conn.external_stop}

        return None


class _CommandConn:

    def __init__(self, external_stop=0):

        self.calls = []
        self.external_stop = external_stop

    def cursor(self):

        return _CommandCursor(self)

    def close(self):

        return None


class ServiceFreshTests(unittest.TestCase):

    def test_session_stays_fresh_for_the_idle_window(self):

        now = datetime(2026, 10, 23, 17, 0, 0)

        self.assertTrue(service_is_fresh("1", now, now, 1800))
        self.assertTrue(service_is_fresh("1", now - timedelta(minutes=30), now, 1800))
        self.assertFalse(
            service_is_fresh("1", now - timedelta(minutes=30, seconds=1), now, 1800)
        )
        self.assertFalse(service_is_fresh("0", now, now, 1800))
        self.assertFalse(service_is_fresh("1", None, now, 1800))


class OperationReadyTests(unittest.TestCase):

    def setUp(self):

        self.now = datetime(2026, 10, 22, 20, 0, 0)
        self.channels = {
            "t3": {"name": "t_gen_in", "ready_min": 75},
            "t6": {"name": "t_cond_in", "ready_max": 28},
        }

    def values(self, gen=80.0, cond=20.0):

        return [None, None, gen, None, None, cond, None, None]

    def series(self, seconds, gen=80.0, cond=20.0, step=5):

        samples = []
        gone = 0

        while gone <= seconds:
            samples.append((
                self.now - timedelta(seconds=seconds - gone),
                self.values(gen, cond),
            ))
            gone += step

        return samples

    def ready(self, samples, hold_s=120):

        return dashboard_ready.operation_ready(
            self.channels,
            samples,
            self.now,
            hold_s=hold_s,
        )

    def test_limits_are_a_generator_minimum_and_a_condenser_ceiling(self):

        self.assertTrue(self.ready(self.series(120), hold_s=120))
        self.assertTrue(self.ready([(self.now, self.values(75, 27.9))], hold_s=0))
        self.assertFalse(self.ready([(self.now, self.values(74.9, 20))], hold_s=0))
        self.assertFalse(self.ready([(self.now, self.values(80, 28))], hold_s=0))
        wide = {
            "t3": {"name": "t_gen_in", "ready_min": 75, "ready_hyst": 2},
            "t6": {"name": "t_cond_in", "ready_max": 28},
        }
        self.assertFalse(dashboard_ready.generator_below_stop(wide, self.values(73, 20)))
        self.assertTrue(dashboard_ready.generator_below_stop(wide, self.values(72.9, 20)))
        self.assertTrue(dashboard_ready.generator_cold(wide, self.values(74, 20)))
        self.assertFalse(dashboard_ready.channel_in_limit(wide["t3"], 76.9))
        self.assertTrue(dashboard_ready.channel_in_limit(wide["t3"], 77))
        self.assertFalse(dashboard_ready.operation_ready(
            wide, [(self.now, self.values(76.9, 20))], self.now, hold_s=0,
        ))
        self.assertTrue(dashboard_ready.operation_ready(
            wide, [(self.now, self.values(77, 20))], self.now, hold_s=0,
        ))
        ceiling = {
            "t3": {"name": "t_gen_in", "ready_min": 75},
            "t6": {
                "name": "t_cond_in",
                "ready_max": 28,
                "ready_hyst": 1,
                "ready_max_stable": 30,
            },
        }
        self.assertFalse(dashboard_ready.condenser_high(ceiling, self.values(80, 29)))
        self.assertTrue(dashboard_ready.condenser_high(ceiling, self.values(80, 29.1)))
        self.assertFalse(dashboard_ready.condenser_high(
            ceiling, self.values(80, 31), stable=True,
        ))
        self.assertTrue(dashboard_ready.condenser_high(
            ceiling, self.values(80, 31.1), stable=True,
        ))
        self.assertFalse(dashboard_ready.condenser_below_start(ceiling, self.values(80, 27)))
        self.assertTrue(dashboard_ready.condenser_below_start(ceiling, self.values(80, 26.9)))
        self.assertFalse(dashboard_ready.channel_in_limit(ceiling["t6"], 27))
        self.assertTrue(dashboard_ready.channel_in_limit(ceiling["t6"], 26.9))
        self.assertFalse(dashboard_ready.operation_ready(
            ceiling, [(self.now, self.values(80, 27))], self.now, hold_s=0,
        ))
        self.assertTrue(dashboard_ready.operation_ready(
            ceiling, [(self.now, self.values(80, 26.9))], self.now, hold_s=0,
        ))

    def test_missing_or_stale_sample_is_not_ready(self):

        self.assertFalse(self.ready([(self.now, self.values(None, 20))], hold_s=0))
        self.assertFalse(self.ready(
            [(self.now - timedelta(seconds=10.1), self.values())],
            hold_s=0,
        ))
        self.assertTrue(self.ready(
            [(self.now - timedelta(seconds=10), self.values())],
            hold_s=0,
        ))
        self.assertFalse(dashboard_ready.operation_ready(self.channels, [], self.now, hold_s=0))

    def test_both_limits_must_hold_for_the_whole_window(self):

        self.assertFalse(self.ready(self.series(60)))
        held = self.series(120)
        self.assertTrue(self.ready(held))
        held[12] = (held[12][0], self.values(70, 20))
        self.assertFalse(self.ready(held))

    def test_a_gap_in_the_samples_breaks_the_hold(self):

        early = self.series(120)
        late_start = self.now - timedelta(seconds=40)
        late = []
        gone = 0
        while gone <= 40:
            late.append((late_start + timedelta(seconds=gone), self.values()))
            gone += 5
        self.assertFalse(self.ready(early[:8] + late))

    def test_configured_start_limits(self):

        cfg = load_config()

        self.assertEqual(cfg["channels"]["t3"]["ready_min"], 80)
        self.assertEqual(cfg["channels"]["t3"]["ready_hyst"], 1)
        self.assertNotIn("ready_max", cfg["channels"]["t3"])
        self.assertEqual(cfg["channels"]["t6"]["ready_max"], 28)
        self.assertEqual(cfg["channels"]["t6"]["ready_max_stable"], 30)
        self.assertEqual(cfg["channels"]["t6"]["ready_hyst"], 1)
        self.assertNotIn("ready_min", cfg["channels"]["t6"])
        self.assertEqual(cfg["channels"]["t1"]["ready_min"], 18)
        self.assertEqual(cfg["channels"]["t1"]["ready_hyst"], 1)
        self.assertNotIn("ready_max", cfg["channels"]["t1"])
        evap = {"t1": {"name": "t_evap_in", "ready_min": 18, "ready_hyst": 1}}
        cold = [16.9, None, 80, None, None, 20, None, None]
        edge = [17.0, None, 80, None, None, 20, None, None]
        top = [19.0, None, 80, None, None, 20, None, None]
        warm = [19.1, None, 80, None, None, 20, None, None]
        self.assertEqual(dashboard_ready.evaporator_band(evap, cold)[1], "low")
        self.assertEqual(dashboard_ready.evaporator_band(evap, edge)[1], "hold")
        self.assertEqual(dashboard_ready.evaporator_band(evap, top)[1], "hold")
        self.assertEqual(dashboard_ready.evaporator_band(evap, warm)[1], "ok")
        self.assertIsNone(dashboard_ready.evaporator_band(evap, [None, None, 80, None, None, 20, None, None])[1])
        self.assertEqual(cfg["ck_3083es_8ch"]["start"]["hold_s"], 120)
        self.assertEqual(cfg["ck_3083es_8ch"]["start"]["stop_hold_s"], 15)
        self.assertEqual(cfg["alarms"]["ready_max_age_s"], 10)
        self.assertEqual(cfg["alarms"]["ready_max_gap_s"], 15)
        self.assertEqual(cfg["alarms"]["cavitation_max_age_s"], 15)
        self.assertEqual(cfg["alarms"]["cavitation_arm_lookback_s"], 10800)
        self.assertEqual(dashboard_ready.ready_max_age_s(cfg), 10)
        self.assertEqual(dashboard_ready.ready_max_gap_s(cfg), 15)
        self.assertEqual(dashboard_ready.ready_max_age_s({"alarms": {"ready_max_age_s": 20}}), 20)


if __name__ == "__main__":
    unittest.main()


class ChannelLabelTests(unittest.TestCase):

    def test_label_is_shown_and_name_kept_for_lookup(self):

        cfg = {"channels": {
            "t1": {"name": "t_evap_in", "label": "t-evap_in", "unit": "°C"},
            "t2": {"name": "t_gen_out", "unit": "°C"},
            "t8": {"name": "NA", "label": "x", "unit": "°C"},
        }}

        names, units, ids = dashboard.build_channel_cfg("t", cfg, ids=True)

        self.assertEqual(names[:2], ["t-evap_in", "t_gen_out"])
        self.assertEqual(ids[:2], ["t_evap_in", "t_gen_out"])
        self.assertEqual(names[7], "NA")
