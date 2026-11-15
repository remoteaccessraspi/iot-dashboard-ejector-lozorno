import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

CK = "config/devices/ck_3083es_8ch.yaml"
GD20 = "config/devices/invt_gd20.yaml"
EM2RS = "config/devices/em2rs_556.yaml"
COMMON = "config/common.yaml"
EMAILS = "config/emails.yaml"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Key:

    key: str
    file: str
    path: tuple
    type: str
    soft: tuple = None
    hard: tuple = None
    label: str = ""

    @property
    def restart(self):

        return self.file != EMAILS


def _k(key, file, path, type, soft=None, hard=None, label=""):

    return Key(key, file, tuple(path.split(".")), type, soft, hard, label)


KEYS = {k.key: k for k in (
    _k("start.hold_s", CK, "ck_3083es_8ch.start.hold_s", "int", (30, 600), (5, 3600), "štart a teplotná obnova, s"),
    _k("start.stop_hold_s", CK, "ck_3083es_8ch.start.stop_hold_s", "int", (5, 120), (1, 3600), "trvanie stop hrany, s"),
    _k("channels.t3.ready_min", CK, "channels.t3.ready_min", "float", (60, 110), (0, 150), "stred generátora t_gen_in, °C"),
    _k("channels.t3.ready_hyst", CK, "channels.t3.ready_hyst", "float", (0, 10), (0, 30), "hysteréza generátora, °C"),
    _k("channels.t6.ready_max", CK, "channels.t6.ready_max", "float", (15, 40), (0, 100), "stred kondenzátora t_cond_in, °C"),
    _k("channels.t6.ready_max_stable", CK, "channels.t6.ready_max_stable", "float", (15, 40), (0, 100), "stred kondenzátora pri stabilnom INVT, °C"),
    _k("channels.t6.ready_hyst", CK, "channels.t6.ready_hyst", "float", (0, 10), (0, 30), "hysteréza kondenzátora, °C"),
    _k("channels.t1.ready_min", CK, "channels.t1.ready_min", "float", (5, 35), (-20, 60), "stred výparníka t_evap_in, °C"),
    _k("channels.t1.ready_hyst", CK, "channels.t1.ready_hyst", "float", (0, 10), (0, 30), "hysteréza výparníka, °C"),
    _k("cavitation.enabled", GD20, "invt_gd20.cavitation.enabled", "bool", label="dohľad kavitácie"),
    _k("cavitation.min_kpa", GD20, "invt_gd20.cavitation.min_kpa", "float", (200, 1400), (0, 1500), "prah AI2, kPa"),
    _k("cavitation.confirm_s", GD20, "invt_gd20.cavitation.confirm_s", "int", (5, 120), (1, 3600), "potvrdenie kavitácie, s"),
    _k("cavitation.frequency_limit_hz", GD20, "invt_gd20.cavitation.frequency_limit_hz", "float", (20, 50), (1, 100), "frekvencia kavitácie, Hz"),
    _k("alarms.loop_low_ma", COMMON, "alarms.loop_low_ma", "float", (0, 4), (0, 4), "dolná hranica slučky, mA"),
    _k("alarms.loop_high_ma", COMMON, "alarms.loop_high_ma", "float", (15, 25), (15, 25), "horná hranica slučky, mA"),
    _k("alarms.loop_max_age_s", COMMON, "alarms.loop_max_age_s", "int", (5, 60), (1, 600), "vek vzorky slučky, s"),
    _k("alarms.ready_max_age_s", COMMON, "alarms.ready_max_age_s", "int", (5, 60), (1, 600), "vek teploty a polohy ventilu, s"),
    _k("alarms.ready_max_gap_s", COMMON, "alarms.ready_max_gap_s", "int", (5, 60), (1, 600), "medzera vzoriek pri hold, s"),
    _k("alarms.cavitation_max_age_s", COMMON, "alarms.cavitation_max_age_s", "int", (5, 60), (1, 600), "vek vzorky meniča pri kavitácii, s"),
    _k("alarms.cavitation_arm_lookback_s", COMMON, "alarms.cavitation_arm_lookback_s", "int", (600, 86400), (60, 604800), "história dosiahnutia prahu AI2, s"),
    _k("alarms.comm_fail_cycles", COMMON, "alarms.comm_fail_cycles", "int", (2, 10), (1, 100), "cykly bez odpovede do alarmu"),
    _k("hmi.service_idle_min", COMMON, "hmi.service_idle_min", "int", (5, 240), (1, 1440), "nečinnosť servisu, min"),
    _k("valve.park_percent", EM2RS, "em2rs_556.valve.park_percent", "float", (0, 100), (0, 100), "park ventilu, %"),
    _k("valve.closed_stop_percent", EM2RS, "em2rs_556.valve.closed_stop_percent", "percent_or_na", (0, 10), (0, 100), "STOP pri zatvorenom ventile, %"),
    _k("recipients", EMAILS, "recipients", "emails", label="príjemcovia alarmových mailov"),
)}


class InvalidValue(Exception):
    pass


def _get(tree, path):

    for part in path:
        if not isinstance(tree, dict) or part not in tree:
            raise KeyError(".".join(path))
        tree = tree[part]

    return tree


def read_values(root=ROOT):

    trees = {}
    values = {}

    for item in KEYS.values():
        if item.file not in trees:
            trees[item.file] = yaml.safe_load((Path(root) / item.file).read_text(encoding="utf-8")) or {}
        values[item.key] = _get(trees[item.file], item.path)

    return values


def _number(value, item):

    if isinstance(value, bool):
        raise InvalidValue(f"{item.key}: čakal som číslo")

    if isinstance(value, str):
        try:
            value = float(value.strip().replace(",", "."))
        except ValueError:
            raise InvalidValue(f"{item.key}: {value!r} nie je číslo") from None

    if not isinstance(value, (int, float)):
        raise InvalidValue(f"{item.key}: čakal som číslo")

    if item.type == "int":
        if value != int(value):
            raise InvalidValue(f"{item.key}: musí byť celé číslo")
        return int(value)

    value = float(value)
    return int(value) if value.is_integer() else value


def normalize(item, value):

    if item.type == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "áno", "ano", "zapnuté", "on", "1"):
            return True
        if text in ("false", "nie", "vypnuté", "off", "0"):
            return False
        raise InvalidValue(f"{item.key}: čakal som áno alebo nie")

    if item.type == "emails":
        if not isinstance(value, list):
            raise InvalidValue(f"{item.key}: čakal som zoznam adries")
        out = []
        for entry in value:
            text = str(entry).strip()
            if not EMAIL_RE.match(text):
                raise InvalidValue(f"{item.key}: {text!r} nie je platná adresa")
            if text not in out:
                out.append(text)
        if not out:
            raise InvalidValue(f"{item.key}: zoznam nesmie byť prázdny")
        if len(out) > 20:
            raise InvalidValue(f"{item.key}: najviac 20 adries")
        return out

    if item.type == "percent_or_na" and isinstance(value, str) and value.strip().lower() == "na":
        return "na"

    return _number(value, item)


def _outside(value, bounds):

    return isinstance(value, (int, float)) and not isinstance(value, bool) and bounds and not (
        bounds[0] <= value <= bounds[1]
    )


def check(changes, current):

    """Vráti (normalizované zmeny, chyby, kľúče mimo rozumného rozsahu)."""

    accepted = {}
    errors = []
    confirm = []

    for change in changes:
        item = KEYS.get(change.get("key"))

        if item is None:
            errors.append(f"Kľúč {change.get('key')!r} Setup nemení.")
            continue

        try:
            value = normalize(item, change.get("new"))
        except InvalidValue as e:
            errors.append(str(e))
            continue

        if _outside(value, item.hard):
            errors.append(f"{item.key}: {value} je mimo {item.hard[0]} až {item.hard[1]}.")
            continue

        if value == current[item.key]:
            errors.append(f"{item.key}: hodnota už je {value}.")
            continue

        accepted[item.key] = value

        if _outside(value, item.soft):
            confirm.append(item.key)

    broken = _relations({**current, **accepted}, accepted)

    if broken:
        return {}, errors + broken, []

    return accepted, errors, confirm


def _relations(v, touched):

    out = []

    def hit(*keys):
        return any(k in touched for k in keys)

    if hit("start.hold_s", "start.stop_hold_s") and v["start.stop_hold_s"] >= v["start.hold_s"]:
        out.append("start.stop_hold_s musí byť kratší ako start.hold_s.")

    if hit("channels.t6.ready_max", "channels.t6.ready_max_stable") and (
        v["channels.t6.ready_max_stable"] <= v["channels.t6.ready_max"]
    ):
        out.append("channels.t6.ready_max_stable musí byť nad channels.t6.ready_max.")

    if hit("alarms.loop_low_ma", "alarms.loop_high_ma") and v["alarms.loop_low_ma"] >= v["alarms.loop_high_ma"]:
        out.append("alarms.loop_low_ma musí ostať pod alarms.loop_high_ma.")

    return out


def _fmt(value):

    return f"{value:g}".replace(".", ",")


def edges(values, touched):

    """Prepočítané hrany kanálov, ktorých sa zmena dotkla."""

    out = []
    v = values
    h3, h6, h1 = (max(0, v[f"channels.{c}.ready_hyst"]) for c in ("t3", "t6", "t1"))

    if any(k.startswith("channels.t3.") for k in touched):
        m = v["channels.t3.ready_min"]
        out.append(f"Generátor t_gen_in: štart od {_fmt(m + h3)} °C, stop pod {_fmt(m - h3)} °C.")

    if any(k.startswith("channels.t6.") for k in touched):
        m = v["channels.t6.ready_max"]
        s = v["channels.t6.ready_max_stable"]
        out.append(
            f"Kondenzátor t_cond_in: štart pod {_fmt(m - h6)} °C, stop nad {_fmt(m + h6)} °C, "
            f"pri stabilnom INVT stop nad {_fmt(s + h6)} °C."
        )

    if any(k.startswith("channels.t1.") for k in touched):
        m = v["channels.t1.ready_min"]
        out.append(f"Výparník t_evap_in: stop pod {_fmt(m - h1)} °C, obnova nad {_fmt(m + h1)} °C.")

    return out
