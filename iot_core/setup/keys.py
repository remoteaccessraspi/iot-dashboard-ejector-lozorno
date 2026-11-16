import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

CK = "config/devices/ck_3083es_8ch.yaml"
CK7082 = "config/devices/ck_7082e_8ch.yaml"
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
    _k("start.hold_s", CK, "ck_3083es_8ch.start.hold_s", "int", (30, 600), (5, 3600), "start and temperature recovery, s"),
    _k("start.stop_hold_s", CK, "ck_3083es_8ch.start.stop_hold_s", "int", (5, 120), (1, 3600), "stop-edge duration, s"),
    _k("channels.t3.ready_min", CK, "channels.t3.ready_min", "float", (60, 110), (0, 150), "generator centre t_gen_in, °C"),
    _k("channels.t3.ready_hyst", CK, "channels.t3.ready_hyst", "float", (0, 10), (0, 30), "generator hysteresis, °C"),
    _k("channels.t6.ready_max", CK, "channels.t6.ready_max", "float", (15, 40), (0, 100), "condenser centre t_cond_in, °C"),
    _k("channels.t6.ready_max_stable", CK, "channels.t6.ready_max_stable", "float", (15, 40), (0, 100), "condenser centre with stable INVT, °C"),
    _k("channels.t6.ready_hyst", CK, "channels.t6.ready_hyst", "float", (0, 10), (0, 30), "condenser hysteresis, °C"),
    _k("channels.t1.ready_min", CK, "channels.t1.ready_min", "float", (5, 35), (-20, 60), "evaporator centre t_evap_in, °C"),
    _k("channels.t1.ready_hyst", CK, "channels.t1.ready_hyst", "float", (0, 10), (0, 30), "evaporator hysteresis, °C"),
    _k("cavitation.enabled", GD20, "invt_gd20.cavitation.enabled", "bool", label="cavitation watch"),
    _k("cavitation.min_kpa", GD20, "invt_gd20.cavitation.min_kpa", "float", (200, 1400), (0, 1500), "AI2 threshold, kPa"),
    _k("cavitation.confirm_s", GD20, "invt_gd20.cavitation.confirm_s", "int", (5, 120), (1, 3600), "cavitation confirm, s"),
    _k("cavitation.frequency_limit_hz", GD20, "invt_gd20.cavitation.frequency_limit_hz", "float", (20, 50), (1, 100), "cavitation frequency, Hz"),
    _k("alarms.loop_low_ma", COMMON, "alarms.loop_low_ma", "float", (0, 4), (0, 4), "loop low limit, mA"),
    _k("alarms.loop_high_ma", COMMON, "alarms.loop_high_ma", "float", (15, 25), (15, 25), "loop high limit, mA"),
    _k("alarms.loop_max_age_s", COMMON, "alarms.loop_max_age_s", "int", (5, 60), (1, 600), "loop sample age, s"),
    _k("alarms.ready_max_age_s", COMMON, "alarms.ready_max_age_s", "int", (5, 60), (1, 600), "temperature and valve-position age, s"),
    _k("alarms.ready_max_gap_s", COMMON, "alarms.ready_max_gap_s", "int", (5, 60), (1, 600), "sample gap during hold, s"),
    _k("alarms.cavitation_max_age_s", COMMON, "alarms.cavitation_max_age_s", "int", (5, 60), (1, 600), "drive sample age for cavitation, s"),
    _k("alarms.cavitation_arm_lookback_s", COMMON, "alarms.cavitation_arm_lookback_s", "int", (600, 86400), (60, 604800), "AI2 threshold history, s"),
    _k("alarms.comm_fail_cycles", COMMON, "alarms.comm_fail_cycles", "int", (2, 10), (1, 100), "cycles without a reply before alarm"),
    _k("hmi.service_idle_min", COMMON, "hmi.service_idle_min", "int", (5, 240), (1, 1440), "service idle, min"),
    _k("valve.park_percent", EM2RS, "em2rs_556.valve.park_percent", "float", (0, 100), (0, 100), "valve park, %"),
    _k("valve.closed_stop_percent", EM2RS, "em2rs_556.valve.closed_stop_percent", "percent_or_na", (0, 10), (0, 100), "STOP with the valve closed, %"),
    _k("recipients", EMAILS, "recipients", "emails", label="alarm mail recipients"),
    _k("card.ck_3083es_8ch", CK, "ck_3083es_8ch.alias", "text", label="card name, temperatures CK-3083ES"),
    _k("card.ck_7082e_8ch", CK7082, "ck_7082e_8ch.alias", "text", label="card name, current loops CK-7082E"),
    _k("card.invt_gd20", GD20, "invt_gd20.alias", "text", label="card name, drive INVT GD20"),
    _k("card.em2rs_556", EM2RS, "em2rs_556.alias", "text", label="card name, valve EM2RS-556"),
)}

CHANNEL_LABELS = {
    "t1": (CK, "t_evap_in"), "t2": (CK, "t_gen_out"), "t3": (CK, "t_gen_in"), "t4": (CK, "t_control"),
    "t5": (CK, "t_cond_out"), "t6": (CK, "t_cond_in"), "t7": (CK, "t_evap_out"),
    "p4": (CK7082, "condenser_flow"), "p5": (CK7082, "evaporator_flow"), "p6": (CK7082, "p_gen_prim"),
    "p7": (CK7082, "p_evap_prim"), "p8": (CK7082, "p_cond_prim"),
}

for _ch, (_file, _name) in CHANNEL_LABELS.items():
    _item = _k(f"channels.{_ch}.label", _file, f"channels.{_ch}.label", "text",
               label=f"display name of {_ch}, internal {_name}")
    KEYS[_item.key] = _item

CARD_KEYS = tuple(k for k in KEYS if k.startswith("card."))
LABEL_GROUPS = tuple(
    tuple(f"channels.{c}.label" for c in CHANNEL_LABELS if c[0] == prefix) for prefix in ("t", "p")
)
CARD_NAME_MAX = 24


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
        raise InvalidValue(f"{item.key}: expected a number")

    if isinstance(value, str):
        try:
            value = float(value.strip().replace(",", "."))
        except ValueError:
            raise InvalidValue(f"{item.key}: {value!r} is not a number") from None

    if not isinstance(value, (int, float)):
        raise InvalidValue(f"{item.key}: expected a number")

    if item.type == "int":
        if value != int(value):
            raise InvalidValue(f"{item.key}: must be a whole number")
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
        raise InvalidValue(f"{item.key}: expected yes or no")

    if item.type == "emails":
        if not isinstance(value, list):
            raise InvalidValue(f"{item.key}: expected a list of addresses")
        out = []
        for entry in value:
            text = str(entry).strip()
            if not EMAIL_RE.match(text):
                raise InvalidValue(f"{item.key}: {text!r} is not a valid address")
            if text not in out:
                out.append(text)
        if not out:
            raise InvalidValue(f"{item.key}: the list must not be empty")
        if len(out) > 20:
            raise InvalidValue(f"{item.key}: at most 20 addresses")
        return out

    if item.type == "text":
        if not isinstance(value, str):
            raise InvalidValue(f"{item.key}: expected text")
        text = " ".join(value.split())
        if not text or text.lower() == "na":
            raise InvalidValue(f"{item.key}: the name must not be empty or NA")
        if len(text) > CARD_NAME_MAX:
            raise InvalidValue(f"{item.key}: at most {CARD_NAME_MAX} characters")
        if not text.isprintable() or "#" in text:
            raise InvalidValue(f"{item.key}: contains a control character or #")
        return text

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
            errors.append(f"Setup does not change key {change.get('key')!r}.")
            continue

        try:
            value = normalize(item, change.get("new"))
        except InvalidValue as e:
            errors.append(str(e))
            continue

        if _outside(value, item.hard):
            errors.append(f"{item.key}: {value} is outside {item.hard[0]} to {item.hard[1]}.")
            continue

        if value == current[item.key]:
            errors.append(f"{item.key}: value is already {value}.")
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
        out.append("start.stop_hold_s must be shorter than start.hold_s.")

    if hit("channels.t6.ready_max", "channels.t6.ready_max_stable") and (
        v["channels.t6.ready_max_stable"] <= v["channels.t6.ready_max"]
    ):
        out.append("channels.t6.ready_max_stable must be above channels.t6.ready_max.")

    if hit("alarms.loop_low_ma", "alarms.loop_high_ma") and v["alarms.loop_low_ma"] >= v["alarms.loop_high_ma"]:
        out.append("alarms.loop_low_ma must stay below alarms.loop_high_ma.")

    if hit(*CARD_KEYS):
        names = [str(v[k]).strip().lower() for k in CARD_KEYS]
        if len(set(names)) != len(names):
            out.append("Two cards must not have the same name.")

    for group in LABEL_GROUPS:
        if hit(*group):
            names = [str(v[k]).strip().lower() for k in group]
            if len(set(names)) != len(names):
                out.append("Two channels on one card must not have the same display name.")

    return out


def _fmt(value):

    return f"{value:g}"


def edges(values, touched):

    """Prepočítané hrany kanálov, ktorých sa zmena dotkla."""

    out = []
    v = values
    h3, h6, h1 = (max(0, v[f"channels.{c}.ready_hyst"]) for c in ("t3", "t6", "t1"))

    if any(k.startswith("channels.t3.") for k in touched):
        m = v["channels.t3.ready_min"]
        out.append(f"Generator t_gen_in: start from {_fmt(m + h3)} °C, stop below {_fmt(m - h3)} °C.")

    if any(k.startswith("channels.t6.") for k in touched):
        m = v["channels.t6.ready_max"]
        s = v["channels.t6.ready_max_stable"]
        out.append(
            f"Condenser t_cond_in: start below {_fmt(m - h6)} °C, stop above {_fmt(m + h6)} °C, "
            f"with stable INVT stop above {_fmt(s + h6)} °C."
        )

    if any(k.startswith("channels.t1.") for k in touched):
        m = v["channels.t1.ready_min"]
        out.append(f"Evaporator t_evap_in: stop below {_fmt(m - h1)} °C, recovery above {_fmt(m + h1)} °C.")

    return out
