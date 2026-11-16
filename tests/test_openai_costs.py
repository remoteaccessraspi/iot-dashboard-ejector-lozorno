import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import app as dashboard
from iot_core.billing import costs
from tests.test_hmi_service import _AppClient

NOW = datetime(2026, 11, 16, 13, 0, tzinfo=timezone.utc)
CFG = {
    "openai_billing": {
        "enabled": True,
        "project_id": "proj_this",
        "poll_interval_seconds": 600,
        "tracking_start_utc": "2026-11-01T00:00:00Z",
        "currency": "USD",
    }
}


def unix(day, month=11):

    return int(datetime(2026, month, day, tzinfo=timezone.utc).timestamp())


def row(value, project="proj_this", currency="usd"):

    return {"project_id": project, "amount": {"value": value, "currency": currency}}


def bucket(day, rows, month=11):

    start = unix(day, month)
    return {"start_time": start, "end_time": start + 86400, "results": rows}


def page(buckets, more=False, nxt=None):

    return 200, {"object": "page", "data": buckets, "has_more": more, "next_page": nxt}, {}


class OpenAICostsTest(unittest.TestCase):

    def setUp(self):

        self.var = Path(tempfile.mkdtemp())
        self.keys = patch.object(costs, "load_openai_admin_key", return_value="super-secret-admin")
        self.keys.start()

    def tearDown(self):

        self.keys.stop()
        shutil.rmtree(self.var)

    def _refresh(self, pages, cfg=None, key=None):

        calls = []
        waits = []

        def get(url, sent_key):

            calls.append((url, sent_key))
            return pages.pop(0)

        result = costs.refresh(
            cfg if cfg is not None else CFG,
            get=get,
            sleep=waits.append,
            now=NOW,
            var_dir=self.var,
            key=key,
        )
        return result, calls, waits

    def test_sums_only_this_project_for_today_month_and_total(self):

        result, calls, _ = self._refresh([page([
            bucket(16, [row("0.25"), row("9.00", project="proj_other")]),
            bucket(2, [row("0.10"), row("1.00", project=None)]),
            bucket(31, [row("4.00")], month=10),
        ])])

        self.assertEqual(result["today_usd"], "0.250000")
        self.assertEqual(result["month_usd"], "0.350000")
        self.assertEqual(result["total_since_tracking_start_usd"], "0.350000")
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["stale"])
        self.assertIsInstance(result["today_usd"], str)
        self.assertNotIn("super-secret-admin", json.dumps(result))
        self.assertNotIn("super-secret-admin", (self.var / "openai-costs.json").read_text(encoding="utf-8"))
        self.assertIn("group_by=project_id", calls[0][0])
        self.assertEqual(calls[0][1], "super-secret-admin")

    def test_exact_decimal_is_not_a_binary_float(self):

        result, _, _ = self._refresh([page([bucket(16, [row("0.0209696")])])])

        self.assertEqual(result["today_usd"], "0.020970")

    def test_empty_results_are_zero_and_a_later_fetch_replaces_the_day(self):

        self._refresh([page([bucket(16, [row("1.50")])])])
        result, _, _ = self._refresh([page([bucket(16, [])])])
        stored = json.loads((self.var / "openai-costs.json").read_text(encoding="utf-8"))

        self.assertEqual(stored["days"]["2026-11-16"], "0.000000")
        self.assertEqual(result["today_usd"], "0.000000")

    def test_pagination_and_long_ranges_follow_every_page(self):

        cfg = json.loads(json.dumps(CFG))
        cfg["openai_billing"]["tracking_start_utc"] = "2026-01-01T00:00:00Z"
        pages = [
            page([bucket(1, [row("0.10")], month=1)], more=True, nxt="p2"),
            page([bucket(2, [row("0.20")], month=1)]),
            page([bucket(16, [row("0.30")])]),
        ]

        def get(url, sent_key):

            calls.append((url, sent_key))
            return pages.pop(0) if pages else page([])

        calls = []
        result = costs.refresh(cfg, get=get, sleep=lambda _s: None, now=NOW, var_dir=self.var)
        starts = [int(parse_qs(urlparse(url).query)["start_time"][0]) for url, _ in calls]

        self.assertGreater(len(set(starts)), 1)
        self.assertIn("page=p2", calls[1][0])
        self.assertEqual(result["total_since_tracking_start_usd"], "0.600000")

    def test_unauthorized_does_not_retry_or_drop_the_last_value(self):

        self._refresh([page([bucket(16, [row("1.25")])])])
        result, calls, waits = self._refresh([(401, None, {})])

        self.assertEqual(len(calls), 1)
        self.assertEqual(waits, [])
        self.assertTrue(result["stale"])
        self.assertEqual(result["status"], "unauthorized")
        self.assertEqual(result["today_usd"], "1.250000")

    def test_rate_limit_retries_then_keeps_the_new_value(self):

        result, calls, waits = self._refresh([
            (429, None, {"retry_after": "2"}),
            page([bucket(16, [row("0.40")])]),
        ])

        self.assertEqual(len(calls), 2)
        self.assertEqual(waits, [2.0])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["today_usd"], "0.400000")

    def test_timeout_retries_and_stays_stale_without_a_previous_value(self):

        def get(url, key):

            raise costs.BillingError("timeout")

        result = costs.refresh(CFG, get=get, sleep=lambda _s: None, now=NOW, var_dir=self.var)

        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["stale"])
        self.assertEqual(result["today_usd"], "0.000000")
        self.assertIsNone(result["last_successful_update_utc"])

    def test_missing_key_and_project_do_not_call_openai(self):

        self.keys.stop()
        self.keys = patch.object(costs, "load_openai_admin_key", return_value="")
        self.keys.start()
        called = []
        result = costs.refresh(CFG, get=lambda url, key: called.append(url), now=NOW, var_dir=self.var)

        self.assertEqual(called, [])
        self.assertEqual(result["status"], "missing_key")

        cfg = json.loads(json.dumps(CFG))
        cfg["openai_billing"]["project_id"] = ""
        self.keys.stop()
        self.keys = patch.object(costs, "load_openai_admin_key", return_value="super-secret-admin")
        self.keys.start()
        result = costs.refresh(cfg, get=lambda url, key: called.append(url), now=NOW, var_dir=self.var)

        self.assertEqual(called, [])
        self.assertEqual(result["status"], "missing_project")

    def test_non_usd_row_is_ignored(self):

        result, _, _ = self._refresh([page([bucket(16, [row("5.00", currency="eur"), row("0.05")])])])

        self.assertEqual(result["today_usd"], "0.050000")

    def test_route_requires_service_and_hides_the_key(self):

        response = _AppClient(dashboard.app).get("/api/openai/costs")

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("super-secret-admin", response.text)
        self.assertNotIn("api_key", response.text)


if __name__ == "__main__":
    unittest.main()
