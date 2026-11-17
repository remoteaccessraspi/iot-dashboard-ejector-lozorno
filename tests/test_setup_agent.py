import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from iot_core.setup import agent, services
from iot_core.setup.manuals import excerpts
from iot_core.setup.keys import read_values
from iot_core.setup.program import code_sheet, program_sheet, runtime_sheet

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
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


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
        self.assertIn("start from 82", result["proposal"]["edges"][0])
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

    def test_usage_counts_questions(self):

        self._ask({"reply": "x", "understood": "", "question": True, "changes": []})
        summary = agent.usage_summary({}, var_dir=self.var)

        self.assertEqual(summary, {"questions_today": 1, "daily_limit": 100})

    def test_old_usage_file_keeps_question_count(self):

        today = time.strftime("%Y-%m-%d")
        (self.var / "setup-usage.json").write_text(json.dumps({
            "date": today,
            "count": 4,
            "today_tokens": 100,
            "month_usd": 0.5,
        }))

        summary = agent.usage_summary({}, var_dir=self.var)

        self.assertEqual(summary["questions_today"], 4)

    def test_long_text_is_refused_before_call(self):

        with self.assertRaises(agent.AgentError):
            self._ask({}, text="x" * 1001)

    def test_pid_question_attaches_the_drive_manual(self):

        text = excerpts("ako sa nastavuje pid regulator na frekvencnom menici")

        self.assertIn("PID_CONTROL.md", text)
        self.assertIn("P09.04", text)
        self.assertNotIn("/CURSOR_INSTRUCTIONS.md", text)
        self.assertNotIn("CK_TP7", text)
        self.assertNotIn("0x", text)

    def test_stepper_question_gets_the_whole_driver_setup(self):

        text = excerpts("ako je nastaveny step motor driver")

        self.assertIn("EM2RS_556_Cursor_Manuals/CONFIGURATION.md", text)
        self.assertLess(text.index("EM2RS"), text.index("INVT") if "INVT" in text else len(text))
        self.assertIn("Pr5.00", text)
        self.assertIn("0,8 A", text)
        self.assertIn("absolútna poloha", text)
        self.assertNotIn("mechanický predpoklad", text)

    def test_criteria_sentence_attaches_no_manual(self):

        self.assertEqual(excerpts("hystereza generatora 2 stupne"), "")

    def test_wiring_table_reaches_the_model(self):

        _, client = self._ask({"reply": "x", "understood": "", "question": True, "changes": []})
        sent = client.sent["messages"][0]["content"]

        self.assertIn("| t3 | t_gen_in | 7 | 8 | 9 |", sent)
        self.assertIn("| i7, p7 | p_evap_prim | 13 | 14 |", sent)

    def test_secrets_never_reach_model(self):

        _, client = self._ask({"reply": "x", "understood": "", "question": True, "changes": []})
        sent = json.dumps(client.sent["messages"], ensure_ascii=False)

        self.assertNotIn("api_key:", sent)
        self.assertNotIn("password", sent)

    def test_code_sheet_says_what_the_master_writes(self):

        text = code_sheet()

        self.assertIn("Pr0.00 = 200 pulzov na otáčku", text)
        self.assertIn("Pr5.00 = 0,8 A (slovo 8)", text)
        self.assertIn("absolútna poloha", text)
        self.assertIn("P00.01 = 2, len keď menič stojí", text)
        self.assertIn("P00.06 required_value 7 master nezapisuje ani nečíta", text)
        self.assertIn("pressure_interlock", text)
        self.assertIn("pid_defaults", text)
        self.assertNotIn("0x", text)

    def test_runtime_sheet_uses_the_last_sample_and_hides_addresses(self):

        journal = "\n".join([
            "GD20 ts=2026-11-17 14:49:10 f=0.0 fset=35.0 dc=321.1 V=0.0 I=0.0 rpm=0 "
            "sp=0.0 fb=0.0 ai2=97.5 fault=0 ext=False status=3 run=0",
            "EM2RS ts=2026-11-17 14:49:10 status=CONFIG_MATCH pr0=200/200 pr5=8/8 "
            "mode=1 pos=300 speed=50/50 acc=100/100 dec=100/100 pause=0 gd20=no/-811.5",
            "GD20 setup P00.01 0x0001 2 == 2",
            "EM2RS setup pulse_per_revolution 0x0001 100 -> 200",
            "GD20 setup P05.04 0x0504 deferred until STOP",
        ])
        text = runtime_sheet(journal)

        self.assertIn("stojí, STOP", text)
        self.assertIn("kontrolované hodnoty sedia", text)
        self.assertIn("Pr5.00 8/8 (0,8 A)", text)
        self.assertIn("P00.01: sedí, hodnota 2", text)
        self.assertIn("Pr0.00: pri štarte zapísané z 100 na 200", text)
        self.assertIn("P05.04: zápis odložený, kým menič stojí", text)
        self.assertNotIn("0x", text)

    def test_program_sheet_reaches_the_model(self):

        _, client = self._ask(
            {"reply": "x", "understood": "", "question": True, "changes": []},
            text="ako je nastaveny step motor driver",
        )
        sent = "\n".join(item["content"] for item in client.sent["messages"])

        self.assertIn("## Čo kód robí", sent)
        self.assertIn("## Čo program práve hlási", sent)
        self.assertNotIn("0x", program_sheet(""))


class SetupServicesTest(unittest.TestCase):

    def test_restart_pending_after_write(self):

        starts = {"iot-master": 100.0, "iot-db-archive": 100.0, "iot-dashboard": 50.0}

        self.assertTrue(services.restart_pending([{"ts": 60, "restart": True}], starts))
        self.assertFalse(services.restart_pending([{"ts": 40, "restart": True}], starts))
        self.assertFalse(services.restart_pending([{"ts": 60, "restart": False}], starts))
        self.assertFalse(services.restart_pending([{"ts": 60, "restart": True}], None))


if __name__ == "__main__":
    unittest.main()
