from datetime import datetime, timedelta

from pymysql.cursors import DictCursor


READY_CHANNELS = ("t_gen_in", "t_cond_in")
# Predvolené hodnoty. Živé čísla sú v common.yaml, alarms.ready_max_*.
READY_MAX_AGE_S = 10
# Jeden vynechaný poll (5 s) medzeru ešte neporuší.
READY_MAX_GAP_S = 15


def _alarms(cfg):

    block = (cfg or {}).get("alarms")

    return block if isinstance(block, dict) else {}


def _positive_seconds(raw, default):

    if raw is None or raw == "":
        return float(default)

    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float(default)

    if value <= 0:
        return float(default)

    return value


def ready_max_age_s(cfg):

    return _positive_seconds(_alarms(cfg).get("ready_max_age_s"), READY_MAX_AGE_S)


def ready_max_gap_s(cfg):

    return _positive_seconds(_alarms(cfg).get("ready_max_gap_s"), READY_MAX_GAP_S)


def start_hold_s(cfg):

    block = ((cfg or {}).get("ck_3083es_8ch") or {}).get("start") or {}

    try:
        return float(block.get("hold_s", 120))
    except (TypeError, ValueError):
        return 120.0


def channel_hyst(channel):

    if not isinstance(channel, dict):
        return 0.0

    raw = channel.get("ready_hyst")

    if raw is None or raw == "":
        return 0.0

    try:
        hyst = float(raw)
    except (TypeError, ValueError):
        return 0.0

    if hyst < 0:
        return 0.0

    return hyst


def channel_in_limit(channel, value):

    if not isinstance(channel, dict):
        return False

    try:
        number = float(value)
    except (TypeError, ValueError):
        return False

    has_min = channel.get("ready_min") is not None
    has_max = channel.get("ready_max") is not None

    if not has_min and not has_max:
        return False

    # Štart berie dolný prah plus hysterezu.
    if has_min and number < float(channel["ready_min"]) + channel_hyst(channel):
        return False

    # Štart berie strop mínus hysterézu. Pri nule ostáva ostré ready_max.
    if has_max and number >= float(channel["ready_max"]) - channel_hyst(channel):
        return False

    return True


def temperature_channel(channels, name):

    if not isinstance(channels, dict):
        return None, None

    for index in range(1, 9):
        channel = channels.get(f"t{index}")

        if not isinstance(channel, dict) or not isinstance(channel.get("name"), str):
            continue

        if channel["name"].strip() == name:
            return index, channel

    return None, None


def channel_label(channel, fallback):

    label = channel.get("label") if isinstance(channel, dict) else None

    if isinstance(label, str) and label.strip():
        return label.strip()

    return fallback


def temperature_label(channels, name):

    _index, channel = temperature_channel(channels, name)
    return channel_label(channel, name)


def _temperature_value(channels, values, name):

    index, channel = temperature_channel(channels, name)

    if index is None or not isinstance(values, (list, tuple)) or index > len(values):
        return None, None

    return channel, values[index - 1]


def generator_cold(channels, values):

    channel, value = _temperature_value(channels, values, "t_gen_in")

    if channel is None or channel.get("ready_min") is None:
        return False

    try:
        return float(value) < float(channel["ready_min"])
    except (TypeError, ValueError):
        return False


def generator_below_stop(channels, values):

    channel, value = _temperature_value(channels, values, "t_gen_in")

    if channel is None or channel.get("ready_min") is None:
        return False

    try:
        return float(value) < float(channel["ready_min"]) - channel_hyst(channel)
    except (TypeError, ValueError):
        return False


def condenser_stop_center(channel, stable=False):

    if not isinstance(channel, dict) or channel.get("ready_max") is None:
        return None

    if stable and channel.get("ready_max_stable") is not None:
        try:
            return float(channel["ready_max_stable"])
        except (TypeError, ValueError):
            return float(channel["ready_max"])

    return float(channel["ready_max"])


def condenser_high(channels, values, stable=False):

    channel, value = _temperature_value(channels, values, "t_cond_in")
    center = condenser_stop_center(channel, stable)

    if channel is None or center is None:
        return False

    try:
        return float(value) > center + channel_hyst(channel)
    except (TypeError, ValueError):
        return False


def evaporator_band(channels, values):

    channel, value = _temperature_value(channels, values, "t_evap_in")

    if channel is None or channel.get("ready_min") is None:
        return None, None

    if value is None:
        return channel, None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return channel, None

    center = float(channel["ready_min"])
    hyst = channel_hyst(channel)

    if number < center - hyst:
        return channel, "low"

    if number > center + hyst:
        return channel, "ok"

    return channel, "hold"


def condenser_below_start(channels, values):

    channel, value = _temperature_value(channels, values, "t_cond_in")

    if channel is None or channel.get("ready_max") is None:
        return False

    try:
        return float(value) < float(channel["ready_max"]) - channel_hyst(channel)
    except (TypeError, ValueError):
        return False


def temperatures_allow_start(channels, values):

    if not isinstance(channels, dict) or not isinstance(values, (list, tuple)):
        return False

    found = {}

    for index in range(1, 9):
        channel = channels.get(f"t{index}")

        if not isinstance(channel, dict) or not isinstance(channel.get("name"), str):
            continue

        sample = values[index - 1] if index - 1 < len(values) else None
        found[channel["name"].strip()] = (channel, sample)

    for name in READY_CHANNELS:
        pair = found.get(name)

        if pair is None or not channel_in_limit(pair[0], pair[1]):
            return False

    return True


def operation_ready(
    channels,
    samples,
    now,
    hold_s=120,
    max_age_s=READY_MAX_AGE_S,
    max_gap_s=READY_MAX_GAP_S,
):

    if now is None or not samples:
        return False

    parsed = []

    for sample in samples:
        if not sample or sample[0] is None:
            continue
        parsed.append((sample[0], sample[1]))

    if not parsed:
        return False

    parsed.sort(key=lambda item: item[0])
    latest_ts = parsed[-1][0]

    try:
        age = (now - latest_ts).total_seconds()
    except (TypeError, AttributeError):
        return False

    if age < 0 or age > float(max_age_s):
        return False

    if not temperatures_allow_start(channels, parsed[-1][1]):
        return False

    hold = float(hold_s)

    if hold <= 0:
        return True

    trailing = []
    previous = None
    gap = float(max_gap_s)

    for ts, values in parsed:
        if previous is not None:
            try:
                spaced = (ts - previous).total_seconds()
            except (TypeError, AttributeError):
                return False
            if spaced > gap:
                trailing = []

        if temperatures_allow_start(channels, values):
            trailing.append(ts)
        else:
            trailing = []

        previous = ts

    if not trailing:
        return False

    return trailing[0] <= now - timedelta(seconds=hold)


def load_temperature_samples(conn, since):

    with conn.cursor(DictCursor) as cur:
        cur.execute(
            """
            SELECT ts, t1, t2, t3, t4, t5, t6, t7, t8
            FROM temperature
            WHERE ts >= %s
            ORDER BY ts
            """,
            (since,),
        )
        rows = cur.fetchall()

    samples = []

    for row in rows:
        samples.append((row["ts"], [row.get(f"t{index}") for index in range(1, 9)]))

    return samples


def start_allowed(conn, cfg, now=None):

    moment = datetime.now() if now is None else now
    hold = start_hold_s(cfg)
    max_age = ready_max_age_s(cfg)
    max_gap = ready_max_gap_s(cfg)
    since = moment - timedelta(seconds=hold + max_gap)
    samples = load_temperature_samples(conn, since)

    return operation_ready(
        (cfg or {}).get("channels") or {},
        samples,
        moment,
        hold_s=hold,
        max_age_s=max_age,
        max_gap_s=max_gap,
    )
