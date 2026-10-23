"""Shared service-session flag. The dashboard writes it, the master reads it."""

PARAMETER = "hmi_service"
RUN_SOURCE = "service"
_CLOCK_SKEW_S = 5


def service_is_fresh(value, updated_ts, now, idle_s):

    if str(value) != "1" or updated_ts is None or now is None:
        return False

    try:
        age = (now - updated_ts).total_seconds()
    except (TypeError, AttributeError):
        return False

    return -_CLOCK_SKEW_S <= age <= float(idle_s)
