import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from iot_core.setup import agent, services
from iot_core.setup.keys import read_values

ROOT = Path(__file__).resolve().parents[1]


class _Client:

    def __init__(self, answer):

        self.answer = answer
        self.sent = None
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):

        self.sent = kwargs
        content = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        message = SimpleNamespace(content=content)
        usage = SimpleNamespace(
            prompt_tokens=10000,
            completion_tokens=200,
            prompt_tokens_details=SimpleNamespace(cached_tokens=8000),
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


class SetupAgentTest(unittest.TestCase):

    def setUp(self):

        self.var = Path(tempfile.mkdtemp())
        self.values = read_values(ROOT)
        self.secrets = patch.object(agent, "load_openai_secrets", return_value={"api_key": "test"})
        self.secrets.start()

    def tearDown(self):

        self.secrets.stop()
        shutil.rmtree(self.var)

    def _ask(self, answer, text="zmena", cfg=None):

        client = _Client(answer)
        result = agent.ask(text, [], self.values, False, cfg or {}, var_dir=self.var,
                           client_factory=lambda key, timeout: client)
        return result, client

    def test_proposal_is_checked_by_python(self):

        result, client = self._ask({
            "reply": "Navrhujem.",
            "understood": "hysteréza generátora 2",
            "question": False,
            "changes": [{"key": "channels.t3.ready_hyst", "new": "2"}],
        })

        change = result["proposal"]["changes"][0]
        self.assertEqual((change["key"], change["new"], change["confirm"]), ("channels.t3.ready_hyst", 2, False))
        self.assertTrue(result["proposal"]["restart"])
        self.assertIn("štart od 82", result["proposal"]["edges"][0])
        self.assertIn("Manuál agenta Setup", client.sent["messages"][0]["content"])
        self.assertIn("channels.t3.ready_min = 80", client.sent["messages"][1]["content"])

    def test_bad_value_from_model_becomes_error(self):

        result, _ = self._ask({
            "reply": "ok",
            "understood": "",
            "question": False,
            "changes": [{"key": "start.stop_hold_s", "new": "500"}],
        })

        self.assertEqual(result["proposal"]["changes"], [])
        self.assertTrue(result["proposal"]["errors"])

    def test_question_drops_changes(self):

        result, _ = self._ask({
            "reply": "Myslíte stred alebo hranu?",
            "understood": "",
            "question": True,
            "changes": [{"key": "channels.t3.ready_min", "new": "85"}],
        })

        self.assertIsNone(result["proposal"])

    def test_emails_are_split(self):

        result, _ = self._ask({
            "reply": "ok",
            "understood": "",
            "question": False,
            "changes": [{"key": "recipients", "new": "a@example.com, b@example.com"}],
        })

        self.assertEqual(result["proposal"]["changes"][0]["new"], ["a@example.com", "b@example.com"])
        self.assertFalse(result["proposal"]["restart"])

    def test_broken_json_is_reported(self):

        with self.assertRaises(agent.AgentError):
            self._ask("nie je json")

    def test_missing_key_is_reported(self):

        with patch.object(agent, "load_openai_secrets", return_value={}):
            with self.assertRaises(agent.AgentError):
                self._ask({"reply": "x", "understood": "", "question": True, "changes": []})

    def test_daily_limit(self):

        answer = {"reply": "x", "understood": "", "question": True, "changes": []}
        cfg = {"setup_agent": {"daily_limit": 1}}
        self._ask(answer, cfg=cfg)

        with self.assertRaises(agent.AgentError):
            self._ask(answer, cfg=cfg)

    def test_usage_counts_tokens_and_cost(self):

        self._ask({"reply": "x", "understood": "", "question": True, "changes": []})
        summary = agent.usage_summary({}, var_dir=self.var)

        # 2000 nových po 0,40, 8000 z cache po 0,10, 200 výstupných po 1,60 za milión
        self.assertEqual(summary["today_tokens"], 10200)
        self.assertAlmostEqual(summary["month_usd"], 0.00192, places=6)
        self.assertAlmostEqual(summary["left_usd"], 5.0 - 0.0019, places=4)
        self.assertEqual(summary["questions_today"], 1)

    def test_old_usage_file_is_upgraded(self):

        today = time.strftime("%Y-%m-%d")
        (self.var / "setup-usage.json").write_text(json.dumps({"date": today, "count": 4}))

        summary = agent.usage_summary({}, var_dir=self.var)

        self.assertEqual((summary["questions_today"], summary["today_tokens"]), (4, 0))

    def test_spent_budget_stops_agent(self):

        answer = {"reply": "x", "understood": "", "question": True, "changes": []}
        cfg = {"setup_agent": {"monthly_budget_usd": 0.001}}
        self._ask(answer, cfg=cfg)

        with self.assertRaises(agent.AgentError):
            self._ask(answer, cfg=cfg)

    def test_long_text_is_refused_before_call(self):

        with self.assertRaises(agent.AgentError):
            self._ask({}, text="x" * 1001)

    def test_secrets_never_reach_model(self):

        _, client = self._ask({"reply": "x", "understood": "", "question": True, "changes": []})
        sent = json.dumps(client.sent["messages"], ensure_ascii=False)

        self.assertNotIn("api_key:", sent)
        self.assertNotIn("password", sent)


class SetupServicesTest(unittest.TestCase):

    def test_restart_pending_after_write(self):

        starts = {"iot-master": 100.0, "iot-db-archive": 100.0, "iot-dashboard": 50.0}

        self.assertTrue(services.restart_pending([{"ts": 60, "restart": True}], starts))
        self.assertFalse(services.restart_pending([{"ts": 40, "restart": True}], starts))
        self.assertFalse(services.restart_pending([{"ts": 60, "restart": False}], starts))
        self.assertFalse(services.restart_pending([{"ts": 60, "restart": True}], None))


if __name__ == "__main__":
    unittest.main()
