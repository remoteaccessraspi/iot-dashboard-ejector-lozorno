import difflib
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from iot_core.setup import keys, yaml_edit
from iot_core.setup.keys import KEYS, check, edges, read_values

ROOT = Path(__file__).resolve().parents[1]

SAMPLE = {
    "int": 77,
    "float": 12.5,
    "bool": False,
    "percent_or_na": "na",
    "emails": ["a@example.com", "b@example.com"],
    "text": "Temp \"A\"",
}


def _copy_config(target):

    for item in KEYS.values():
        dest = target / item.file
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / item.file, dest)


class SetupEditTest(unittest.TestCase):

    def setUp(self):

        self.tmp = Path(tempfile.mkdtemp())
        _copy_config(self.tmp)

    def tearDown(self):

        shutil.rmtree(self.tmp)

    def test_every_key_exists_in_yaml(self):

        values = read_values(ROOT)

        self.assertEqual(set(values), set(KEYS))

    def test_every_key_is_in_manual_and_not_inactive(self):

        manual = (ROOT / "docs/agent/pravidla.md").read_text(encoding="utf-8")

        for item in KEYS.values():
            self.assertIn(item.path[-1], manual, item.key)
            inactive = [
                line for line in (ROOT / item.file).read_text(encoding="utf-8").splitlines()
                if "NEAKTÍVNE" in line and item.path[-1] in line
            ]
            self.assertEqual(inactive, [], item.key)

    def test_each_key_changes_one_spot_and_keeps_comments(self):

        for item in KEYS.values():
            path = self.tmp / item.file
            before = path.read_text(encoding="utf-8")
            after = yaml_edit.edit_text(before, item.path, SAMPLE[item.type])

            removed = [l for l in difflib.ndiff(before.splitlines(), after.splitlines()) if l.startswith("- ")]
            comments = [l for l in before.splitlines() if l.strip().startswith("#")]

            self.assertTrue(removed, item.key)
            if item.type != "emails":
                self.assertEqual(len(removed), 1, item.key)
            for line in comments:
                self.assertIn(line, after.splitlines(), item.key)

    def test_flow_map_keeps_other_fields(self):

        text = '  t3: { name: "t_gen_in", unit: "°C", ready_min: 80, ready_hyst: 1 }\n'
        doc = "channels:\n" + text

        new = yaml_edit.edit_text(doc, ("channels", "t3", "ready_hyst"), 2.5)

        self.assertEqual(
            yaml.safe_load(new)["channels"]["t3"],
            {"name": "t_gen_in", "unit": "°C", "ready_min": 80, "ready_hyst": 2.5},
        )

    def test_trailing_comment_survives(self):

        doc = "a:\n  b: 3  # pozn\n  c: 4\n"

        self.assertEqual(yaml_edit.edit_text(doc, ("a", "b"), 5), "a:\n  b: 5  # pozn\n  c: 4\n")

    def test_same_name_in_other_block_is_not_touched(self):

        doc = "x:\n  enabled: true\ny:\n  enabled: true\n"

        new = yaml_edit.edit_text(doc, ("y", "enabled"), False)

        self.assertEqual(yaml.safe_load(new), {"x": {"enabled": True}, "y": {"enabled": False}})

    def test_apply_writes_backup_and_log(self):

        old = read_values(self.tmp)["channels.t3.ready_min"]

        entry = yaml_edit.apply(
            [{"key": "channels.t3.ready_min", "old": old, "new": 85}],
            request_text="štart od 86",
            root=self.tmp,
        )

        self.assertEqual(read_values(self.tmp)["channels.t3.ready_min"], 85)
        self.assertTrue(entry["restart"])
        self.assertEqual(len(list((self.tmp / "var/setup-backup").iterdir())), 1)
        self.assertEqual(yaml_edit.history(root=self.tmp)[0]["changes"][0]["new"], 85)

    def test_apply_refuses_when_file_changed(self):

        with self.assertRaises(yaml_edit.Conflict):
            yaml_edit.apply([{"key": "start.hold_s", "old": 1, "new": 60}], root=self.tmp)

        self.assertFalse((self.tmp / "var/setup-changes.jsonl").exists())

    def test_apply_is_all_or_nothing(self):

        values = read_values(self.tmp)

        with self.assertRaises(yaml_edit.Conflict):
            yaml_edit.apply(
                [
                    {"key": "start.hold_s", "old": values["start.hold_s"], "new": 60},
                    {"key": "alarms.loop_low_ma", "old": 99, "new": 3},
                ],
                root=self.tmp,
            )

        self.assertEqual(read_values(self.tmp)["start.hold_s"], values["start.hold_s"])

    def test_emails_do_not_need_restart(self):

        values = read_values(self.tmp)

        entry = yaml_edit.apply(
            [{"key": "recipients", "old": values["recipients"], "new": ["x@example.com"]}],
            root=self.tmp,
        )

        self.assertFalse(entry["restart"])
        self.assertEqual(read_values(self.tmp)["recipients"], ["x@example.com"])


class SetupCheckTest(unittest.TestCase):

    def setUp(self):

        self.values = read_values(ROOT)

    def test_unknown_key_is_refused(self):

        accepted, errors, _ = check([{"key": "modbus.baudrate", "new": 19200}], self.values)

        self.assertEqual(accepted, {})
        self.assertTrue(errors)

    def test_hard_limit_refuses_and_soft_limit_asks(self):

        _, errors, _ = check([{"key": "alarms.loop_low_ma", "new": 6}], self.values)
        accepted, errors2, confirm = check([{"key": "start.hold_s", "new": 900}], self.values)

        self.assertTrue(errors)
        self.assertEqual(errors2, [])
        self.assertEqual(accepted, {"start.hold_s": 900})
        self.assertEqual(confirm, ["start.hold_s"])

    def test_stop_hold_must_stay_below_hold(self):

        _, errors, _ = check([{"key": "start.stop_hold_s", "new": self.values["start.hold_s"]}], self.values)

        self.assertTrue(any("stop_hold_s" in e for e in errors))

    def test_stable_edge_must_stay_above_ready_max(self):

        _, errors, _ = check([{"key": "channels.t6.ready_max", "new": 35}], self.values)

        self.assertTrue(errors)

    def test_closed_stop_accepts_na(self):

        accepted, errors, _ = check([{"key": "valve.closed_stop_percent", "new": "NA"}], self.values)

        self.assertEqual(errors, [])
        self.assertEqual(accepted, {"valve.closed_stop_percent": "na"})

    def test_bad_email_is_refused(self):

        _, errors, _ = check([{"key": "recipients", "new": ["nie-je-mail"]}], self.values)

        self.assertTrue(errors)

    def test_card_name_is_trimmed_and_checked(self):

        accepted, errors, _ = check([{"key": "card.ck_3083es_8ch", "new": "  Temp  "}], self.values)

        self.assertEqual((accepted, errors), ({"card.ck_3083es_8ch": "Temp"}, []))

        for bad in ("", "NA", "x" * 25, "A # B", 5):
            accepted, errors, _ = check([{"key": "card.ck_3083es_8ch", "new": bad}], self.values)
            self.assertEqual(accepted, {}, bad)
            self.assertTrue(errors, bad)

    def test_two_cards_cannot_share_a_name(self):

        accepted, errors, _ = check(
            [{"key": "card.ck_3083es_8ch", "new": self.values["card.invt_gd20"].lower()}], self.values
        )

        self.assertEqual(accepted, {})
        self.assertTrue(errors)

    def test_edges_follow_hysteresis(self):

        values = {**self.values, "channels.t3.ready_min": 80, "channels.t3.ready_hyst": 2}

        self.assertEqual(
            edges(values, ["channels.t3.ready_hyst"]),
            ["Generator t_gen_in: start from 82 °C, stop below 78 °C."],
        )


if __name__ == "__main__":
    unittest.main()
