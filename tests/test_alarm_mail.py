import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from iot_core.mail.alarm_mail import (
    build_alarm_message,
    load_recipients,
    load_smtp,
)


NOW = datetime(2026, 10, 23, 16, 50, 0)


class AlarmMailTest(unittest.TestCase):

    def test_message_names_the_alarm_and_asks_not_to_reply(self):

        message = build_alarm_message(
            {"from": "alarms.remote.raspi@gmail.com"},
            ["remote.access.raspi@gmail.com"],
            {
                "code": "GD20_FAULT",
                "source": "invt_gd20",
                "device_id": 100,
                "class": "ALARM",
                "message": "GD20 fault 37",
                "details": '{"fault_code": 37}',
                "inhibit_run": 1,
                "ts": NOW,
            },
        )
        body = message.get_content()

        self.assertIn("GD20_FAULT", message["Subject"])
        self.assertEqual(message["From"], "alarms.remote.raspi@gmail.com")
        self.assertEqual(message["To"], "remote.access.raspi@gmail.com")
        self.assertEqual(message["Auto-Submitted"], "auto-generated")
        self.assertIn("GD20 fault 37", body)
        self.assertIn("Blokuje chod: áno", body)
        self.assertIn("Na tento email neodpovedajte.", body)

    def test_recipients_and_smtp_come_from_their_files(self):

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            emails = root / "emails.yaml"
            secrets = root / "secrets.yaml"
            emails.write_text(
                "recipients:\n  - a@example.com\n  - b@example.com\n",
                encoding="utf-8",
            )
            secrets.write_text(
                "\n".join(
                    [
                        "smtp:",
                        "  host: smtp.gmail.com",
                        "  port: 587",
                        "  user: alarms.remote.raspi@gmail.com",
                        '  password: "abcd efgh ijkl mnop"',
                        "  from: alarms.remote.raspi@gmail.com",
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                load_recipients(emails),
                ["a@example.com", "b@example.com"],
            )
            smtp = load_smtp(secrets)
            self.assertEqual(smtp["port"], 587)
            self.assertEqual(smtp["password"], "abcdefghijklmnop")

    def test_empty_recipient_list_is_rejected(self):

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "emails.yaml"
            path.write_text("recipients: []\n", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                load_recipients(path)


if __name__ == "__main__":
    unittest.main()
