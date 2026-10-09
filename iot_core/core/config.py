import os
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
SETTINGS_PATH = CONFIG_DIR / "settings.yaml"
SECRETS_PATH = CONFIG_DIR / "secrets.yaml"

# Prihlasovacie údaje k databáze nepatria do verzovaného settings.yaml.
# Prednosť má prostredie, potom secrets.yaml, až nakoniec settings.yaml.
DB_ENV_VARS = {
    "host": "EJECTOR_DB_HOST",
    "port": "EJECTOR_DB_PORT",
    "user": "EJECTOR_DB_USER",
    "password": "EJECTOR_DB_PASSWORD",
    "name": "EJECTOR_DB_NAME",
}


def _secret_database():

    if not SECRETS_PATH.exists():
        return {}

    secrets = yaml.safe_load(SECRETS_PATH.read_text(encoding="utf-8")) or {}
    return secrets.get("database") or {}


def _apply_env(database, keys):

    for key in keys:
        value = os.environ.get(DB_ENV_VARS[key])

        if value:
            database[key] = value


def load_config():

    cfg = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))
    secret_db = _secret_database()

    database = cfg.setdefault("database", {})
    database.update(secret_db)
    _apply_env(database, DB_ENV_VARS)

    # Hot a archív majú vlastný host/port. Používateľ a heslo sú spoločné.
    for section in ("database_hot", "database_archive"):
        extra = cfg.get(section)

        if not isinstance(extra, dict):
            continue

        for key in ("user", "password"):
            if key not in extra and key in secret_db:
                extra[key] = secret_db[key]

        _apply_env(extra, ("user", "password"))

    return cfg
