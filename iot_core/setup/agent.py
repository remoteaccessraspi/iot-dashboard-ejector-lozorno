import json
import time
from pathlib import Path

from iot_core.core.config import load_openai_secrets
from iot_core.setup.keys import KEYS, ROOT, check, edges

MANUAL_PATH = ROOT / "docs/agent/pravidla.md"
MAX_TEXT = 1000
MAX_HISTORY = 20

DEFAULTS = {
    "enabled": True,
    "model": "gpt-4.1-mini",
    "timeout_s": 30,
    "max_output_tokens": 800,
    "daily_limit": 100,
    "monthly_budget_usd": 1.0,
    "price_input_per_mtok": 0.40,
    "price_cached_per_mtok": 0.10,
    "price_output_per_mtok": 1.60,
}

FORMAT = """
## Formát odpovede

Odpovedáš len JSON objektom podľa schémy:

- `reply`: text pre zákazníka po slovensky.
- `understood`: veta zákazníka vlastnými slovami, alebo prázdny reťazec pri otázke a odmietnutí.
- `question`: true, keď sa pýtaš a nič nenavrhuješ.
- `changes`: zoznam zmien. `key` je identifikátor zo zoznamu aktuálnych hodnôt, `new` nová hodnota ako text.
  Pri `recipients` je `new` celý nový zoznam adries oddelený čiarkou. Pri `closed_stop_percent` môže byť `na`.

Starú hodnotu, hrany ani potrebu reštartu do `changes` nepíš. Karta ich vypočíta a ukáže sama.
Keď nič nemeníš, `changes` je prázdny zoznam. Pri odmietnutí je `changes` prázdne.
Nenavrhuj kľúč, ktorého nová hodnota sa rovná súčasnej.
V `reply` nikdy netvrď, že je zmena urobená. Zapíše ju až zákazník tlačidlom Súhlas.
"""


class AgentError(Exception):
    pass


def settings(cfg):

    out = dict(DEFAULTS)
    out.update((cfg or {}).get("setup_agent") or {})
    return out


def _schema():

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "setup_proposal",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["reply", "understood", "question", "changes"],
                "properties": {
                    "reply": {"type": "string"},
                    "understood": {"type": "string"},
                    "question": {"type": "boolean"},
                    "changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["key", "new"],
                            "properties": {
                                "key": {"type": "string", "enum": sorted(KEYS)},
                                "new": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    }


def _state_message(values, drive):

    lines = ["Aktuálne hodnoty povolených kľúčov, čítané práve teraz zo súborov:"]

    for key, item in KEYS.items():
        lines.append(f"- {key} = {json.dumps(values[key], ensure_ascii=False)} ({item.label}; {item.file})")

    lines.append("")
    lines.append({True: "Menič práve beží.", False: "Menič práve stojí."}.get(drive, "Stav meniča nie je známy."))
    return "\n".join(lines)


def build_messages(text, history, values, drive):

    messages = [
        {"role": "system", "content": MANUAL_PATH.read_text(encoding="utf-8") + FORMAT},
        {"role": "system", "content": _state_message(values, drive)},
    ]

    for entry in (history or [])[-MAX_HISTORY:]:
        role = entry.get("role")
        content = entry.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            messages.append({"role": role, "content": content[:4000]})

    messages.append({"role": "user", "content": text})
    return messages


def _new_value(key, raw):

    if KEYS[key].type == "emails" and isinstance(raw, str):
        return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]

    return raw


def proposal(changes, values):

    """Overený návrh pre kartu. Hodnoty od modelu prejdú cez check()."""

    accepted, errors, confirm = check(
        [{"key": c.get("key"), "new": _new_value(c["key"], c.get("new", "")) if c.get("key") in KEYS else c.get("new")}
         for c in changes],
        values,
    )
    merged = {**values, **accepted}

    return {
        "changes": [
            {"key": k, "label": KEYS[k].label, "old": values[k], "new": v, "confirm": k in confirm}
            for k, v in accepted.items()
        ],
        "errors": errors,
        "edges": edges(merged, accepted),
        "restart": any(KEYS[k].restart for k in accepted),
    }


def _usage_path(var_dir):

    return Path(var_dir or ROOT / "var") / "setup-usage.json"


def _load_usage(var_dir):

    try:
        usage = json.loads(_usage_path(var_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        usage = {}

    today = time.strftime("%Y-%m-%d")
    month = today[:7]

    if usage.get("date") != today:
        usage.update(date=today, count=0, today_tokens=0, today_usd=0.0)

    if usage.get("month") != month:
        usage.update(month=month, month_tokens=0, month_usd=0.0)

    for period in ("today", "month", "total"):
        usage.setdefault(f"{period}_tokens", 0)
        usage.setdefault(f"{period}_usd", 0.0)

    return usage


def _save_usage(var_dir, usage):

    path = _usage_path(var_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(usage), encoding="utf-8")


def _reserve(var_dir, opts):

    usage = _load_usage(var_dir)

    if usage["count"] >= int(opts["daily_limit"]):
        raise AgentError("Dnešný limit požiadaviek je vyčerpaný.")

    if usage["month_usd"] >= float(opts["monthly_budget_usd"]):
        raise AgentError("Mesačný rozpočet agenta je minutý.")

    usage["count"] += 1
    _save_usage(var_dir, usage)


def cost_usd(tokens, opts):

    cached = min(tokens.get("cached", 0), tokens.get("input", 0))

    return (
        (tokens.get("input", 0) - cached) * float(opts["price_input_per_mtok"])
        + cached * float(opts["price_cached_per_mtok"])
        + tokens.get("output", 0) * float(opts["price_output_per_mtok"])
    ) / 1_000_000


def _record(var_dir, tokens, opts):

    usage = _load_usage(var_dir)
    count = tokens.get("input", 0) + tokens.get("output", 0)
    usd = cost_usd(tokens, opts)

    for period in ("today", "month", "total"):
        usage[f"{period}_tokens"] += count
        usage[f"{period}_usd"] += usd

    _save_usage(var_dir, usage)


def usage_summary(cfg, var_dir=None):

    opts = settings(cfg)
    usage = _load_usage(var_dir)
    budget = float(opts["monthly_budget_usd"])

    return {
        "questions_today": usage["count"],
        "daily_limit": int(opts["daily_limit"]),
        "today_tokens": usage["today_tokens"],
        "today_usd": round(usage["today_usd"], 6),
        "month_tokens": usage["month_tokens"],
        "month_usd": round(usage["month_usd"], 6),
        "budget_usd": budget,
        "left_usd": round(max(0.0, budget - usage["month_usd"]), 6),
        "total_tokens": usage["total_tokens"],
        "total_usd": round(usage["total_usd"], 6),
    }


def _tokens(response):

    usage = getattr(response, "usage", None)
    details = getattr(usage, "prompt_tokens_details", None)

    return {
        "input": int(getattr(usage, "prompt_tokens", 0) or 0),
        "cached": int(getattr(details, "cached_tokens", 0) or 0),
        "output": int(getattr(usage, "completion_tokens", 0) or 0),
    }


def _client(api_key, timeout):

    from openai import OpenAI

    return OpenAI(api_key=api_key, timeout=timeout, max_retries=1)


def _call(messages, opts, client_factory, var_dir):

    import openai

    api_key = load_openai_secrets().get("api_key")

    if not api_key:
        raise AgentError("Agent nie je nastavený, chýba kľúč.")

    client = client_factory(api_key, float(opts["timeout_s"]))

    try:
        response = client.chat.completions.create(
            model=opts["model"],
            messages=messages,
            response_format=_schema(),
            max_completion_tokens=int(opts["max_output_tokens"]),
            temperature=0.2,
        )
    except openai.AuthenticationError:
        raise AgentError("Kľúč OpenAI neplatí.") from None
    except openai.RateLimitError as e:
        if "quota" in str(e) or "credit" in str(e):
            raise AgentError("Kredit OpenAI je minutý.") from None
        raise AgentError("OpenAI je preťažené. Skúste o chvíľu.") from None
    except (openai.APITimeoutError, openai.APIConnectionError):
        raise AgentError("Agent je nedostupný. Skúste neskôr.") from None
    except openai.APIError as e:
        print("setup agent:", type(e).__name__, getattr(e, "status_code", ""))
        raise AgentError("Agent je nedostupný. Skúste neskôr.") from None

    _record(var_dir, _tokens(response), opts)

    try:
        return json.loads(response.choices[0].message.content)
    except (ValueError, TypeError, IndexError, AttributeError):
        raise AgentError("Agent odpovedal nezrozumiteľne. Skúste vetu inak.") from None


def ask(text, history, values, drive, cfg, var_dir=None, client_factory=_client):

    opts = settings(cfg)

    if not opts["enabled"]:
        raise AgentError("Agent je v common.yaml vypnutý.")

    text = (text or "").strip()

    if not text:
        raise AgentError("Napíšte, čo chcete zmeniť.")

    if len(text) > MAX_TEXT:
        raise AgentError(f"Veta je dlhšia ako {MAX_TEXT} znakov.")

    _reserve(var_dir, opts)
    answer = _call(build_messages(text, history, values, drive), opts, client_factory, var_dir)

    if not isinstance(answer, dict) or not isinstance(answer.get("reply"), str):
        raise AgentError("Agent odpovedal nezrozumiteľne. Skúste vetu inak.")

    changes = [] if answer.get("question") else [c for c in answer.get("changes") or [] if isinstance(c, dict)]

    return {
        "reply": answer["reply"],
        "understood": answer.get("understood") or "",
        "question": bool(answer.get("question")),
        "proposal": proposal(changes, values) if changes else None,
    }
