import smtplib
import socket
import ssl
import threading
import time
from email.message import EmailMessage

import yaml

from iot_core.core.config import CONFIG_DIR, SECRETS_PATH


EMAILS_PATH = CONFIG_DIR / "emails.yaml"
_SMTP_KEYS = ("host", "port", "user", "password", "from")
_TIMEOUT_S = 20
_ATTEMPTS = 2


def load_smtp(path=SECRETS_PATH):

    if not path.is_file():
        raise RuntimeError("chýba config/secrets.yaml")

    secrets = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    smtp = secrets.get("smtp") if isinstance(secrets, dict) else None

    if not isinstance(smtp, dict):
        raise RuntimeError("v secrets.yaml chýba smtp")

    missing = [key for key in _SMTP_KEYS if not smtp.get(key)]

    if missing:
        raise RuntimeError("smtp nemá " + ", ".join(missing))

    smtp = dict(smtp)
    smtp["port"] = int(smtp["port"])
    smtp["password"] = str(smtp["password"]).replace(" ", "")
    return smtp


def load_recipients(path=EMAILS_PATH):

    if not path.is_file():
        raise RuntimeError("chýba config/emails.yaml")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get("recipients") if isinstance(data, dict) else None

    if not isinstance(raw, list):
        raise RuntimeError("emails.yaml nemá zoznam recipients")

    recipients = [str(item).strip() for item in raw if str(item).strip()]

    if not recipients:
        raise RuntimeError("emails.yaml nemá žiadneho príjemcu")

    return recipients


def build_alarm_message(smtp, recipients, alarm):

    host = socket.gethostname()
    code = alarm.get("code") or "ALARM"
    source = alarm.get("source") or "-"
    when = alarm.get("ts")
    blocks = int(alarm.get("inhibit_run") or 0) == 1
    msg = EmailMessage()
    msg["Subject"] = f"ALARM {host} {code}"
    msg["From"] = smtp["from"]
    msg["To"] = ", ".join(recipients)
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(
        "\n".join(
            [
                f"Alarm na {host}.",
                "",
                f"Kód: {code}",
                f"Zdroj: {source}",
                f"Zariadenie: {alarm.get('device_id')}",
                f"Správa: {alarm.get('message') or '-'}",
                f"Detail: {alarm.get('details') or '-'}",
                f"Vznik: {when}",
                f"Blokuje chod: {'áno' if blocks else 'nie'}",
                "",
                "Na tento email neodpovedajte.",
            ]
        )
    )
    return msg


def send_alarm_mail(alarm):

    smtp_cfg = load_smtp()
    recipients = load_recipients()
    message = build_alarm_message(smtp_cfg, recipients, alarm)
    last_error = None

    for attempt in range(1, _ATTEMPTS + 1):

        try:
            _send(smtp_cfg, message)
            print(
                "alarm mail: odoslané",
                message["Subject"],
                "->",
                ", ".join(recipients),
            )
            return

        except Exception as exc:
            last_error = exc
            print(f"alarm mail: pokus {attempt} zlyhal: {exc}")

            if attempt < _ATTEMPTS:
                time.sleep(3)

    raise last_error


def schedule_alarm_mail(alarm):

    snapshot = dict(alarm)

    threading.Thread(
        target=_safe_send,
        args=(snapshot,),
        name="alarm-mail",
        daemon=True,
    ).start()


def _safe_send(alarm):

    try:
        send_alarm_mail(alarm)
    except Exception as exc:
        print("alarm mail:", exc)


def _send(smtp_cfg, message):

    context = ssl.create_default_context()

    with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=_TIMEOUT_S) as smtp:
        smtp.ehlo(socket.gethostname())
        smtp.starttls(context=context)
        smtp.ehlo(socket.gethostname())
        smtp.login(smtp_cfg["user"], smtp_cfg["password"])
        smtp.send_message(message)
