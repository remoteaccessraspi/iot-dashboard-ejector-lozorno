import hashlib
import hmac


SERVICE_COOKIE = "hmi_service"


def idle_seconds(minutes):

    try:
        whole = int(minutes)
    except (TypeError, ValueError):
        whole = 30

    if whole < 1:
        return 30 * 60

    return whole * 60


def session_secret(hmi):

    if not isinstance(hmi, dict):
        return None

    secret = hmi.get("session_secret")

    if not isinstance(secret, str) or secret == "":
        return None

    return secret


def password_matches(submitted, hmi):

    if not isinstance(submitted, str) or not isinstance(hmi, dict):
        return False

    if "service_password" not in hmi:
        return False

    expected = hmi.get("service_password")

    if not isinstance(expected, str):
        return False

    return hmac.compare_digest(
        submitted.encode("utf-8"),
        expected.encode("utf-8"),
    )


def sign_session(secret, expiry):

    if not isinstance(secret, str) or secret == "":
        raise ValueError("session secret is missing")

    payload = str(int(expiry)).encode("ascii")
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    return payload.decode("ascii") + "." + digest


def read_session(secret, token, now):

    if not isinstance(secret, str) or secret == "" or not isinstance(token, str):
        return None

    payload, dot, digest = token.partition(".")

    if dot != "." or not payload.isdigit() or digest == "":
        return None

    expected = hmac.new(
        secret.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(digest, expected):
        return None

    expiry = int(payload)

    if expiry <= now:
        return None

    return expiry
