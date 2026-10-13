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


def _load_yaml(path):

    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise RuntimeError(f"{path.name} nie je slovník nastavení")

    return data


def _included_path(entry):

    if not isinstance(entry, str) or not entry or entry.startswith(("/", "\\")):
        raise RuntimeError(f"Neplatný include: {entry!r}")

    path = (CONFIG_DIR / entry).resolve()
    root = CONFIG_DIR.resolve()

    if path != root and root not in path.parents:
        raise RuntimeError(f"Include mimo config: {entry}")

    if path == SETTINGS_PATH.resolve():
        raise RuntimeError("settings.yaml nemôže includeovať sám seba")

    if not path.is_file():
        raise RuntimeError(f"Chýba súbor nastavenia: {entry}")

    return path


def _merge(base, extra, source):

    for key, value in extra.items():
        here = f"{source}:{key}" if isinstance(key, str) else str(key)

        if key not in base:
            base[key] = value
            continue

        current = base[key]

        if isinstance(current, dict) and isinstance(value, dict):
            _merge(current, value, f"{source}:{key}")
            continue

        if current != value:
            raise RuntimeError(
                f"Konflikt nastavenia {here}: {current!r} vs {value!r}"
            )

    return base


def merge_includes(includes):

    if not isinstance(includes, list) or not includes:
        raise RuntimeError("settings.yaml include musí byť neprázdny zoznam")

    merged = {}

    for entry in includes:
        path = _included_path(entry)
        _merge(merged, _load_yaml(path), entry)

    return merged


def load_settings():

    root = _load_yaml(SETTINGS_PATH)
    includes = root.get("include")

    if not isinstance(includes, list):
        return root

    extra = set(root) - {"include"}

    if extra:
        raise RuntimeError(
            "settings.yaml so zoznamom include nemá mať ďalšie kľúče: "
            + ", ".join(sorted(extra))
        )

    return merge_includes(includes)


def load_config():

    cfg = load_settings()
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
