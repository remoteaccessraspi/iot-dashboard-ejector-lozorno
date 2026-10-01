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


def load_config():

    cfg = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))

    database = cfg.setdefault("database", {})

    if SECRETS_PATH.exists():
        secrets = yaml.safe_load(SECRETS_PATH.read_text(encoding="utf-8")) or {}
        database.update(secrets.get("database") or {})

    for key, env_var in DB_ENV_VARS.items():
        value = os.environ.get(env_var)

        if value:
            database[key] = value

    return cfg
