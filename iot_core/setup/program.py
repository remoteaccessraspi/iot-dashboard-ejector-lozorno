"""Čo master so zariadeniami naozaj robí a čo naposledy hlásil.

Text ide do agenta. Nie sú v ňom adresy registrov ani funkčné kódy.
"""

import re
import subprocess

import yaml

from iot_core.setup.keys import EM2RS, GD20, ROOT

_HEX = re.compile(r"0x[0-9A-Fa-f]+")
_GD20_POLL = re.compile(
    r"GD20 ts=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"f=(\S+) fset=(\S+) dc=\S+ V=\S+ I=\S+ rpm=\S+ "
    r"sp=(\S+) fb=(\S+) ai2=(\S+) fault=(\S+) ext=(\S+) status=(\S+) run=(\S+)"
)
_EM2RS_POLL = re.compile(
    r"EM2RS ts=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"status=(\S+) pr0=(\S+) pr5=(\S+) mode=(\S+) pos=(\S+) "
    r"speed=(\S+) acc=(\S+) dec=(\S+) pause=(\S+) gd20=(\S+)"
)
_SETUP = re.compile(r"(GD20|EM2RS) setup (\S+) (.*)")

_GD20_STATUS = {
    "1": "beh vpred",
    "2": "beh vzad",
    "3": "STOP",
    "4": "porucha",
    "5": "výpadok napájania",
    "6": "prednabudenie",
}
_EM2RS_STATUS = {
    "CONFIG_MATCH": "kontrolované hodnoty sedia",
    "CONFIG_MISMATCH": "niektorá kontrolovaná hodnota sa líši",
    "CONFIG_READ_ERROR": "čítanie pri kontrole zlyhalo",
    "CONFIG_NOT_CHECKED": "kontrola nie je kompletná",
}


def program_sheet(journal=None):

    """Obe správy pre model. journal=None prečíta beh iot-master."""

    parts = [
        "Nastavenie v kóde a posledný beh programu. Keď sa číslo líši od snímky "
        "v pravidlách, ber ho odtiaľto. Vysvetlenie z tejto správy nie je návrh, "
        "changes nechaj prázdne. Adresu registra a funkčný kód do odpovede nepíš. "
        "Čo tu nie je, povedz a nevymýšľaj.",
        "",
        code_sheet(),
        "",
        runtime_sheet(journal),
    ]
    text = "\n".join(parts)
    return _HEX.sub("register", text)


def code_sheet(root=ROOT):

    em2rs = _load(root, EM2RS).get("em2rs_556") or {}
    gd20 = _load(root, GD20).get("invt_gd20") or {}
    lines = ["## Čo kód robí", ""]
    lines.append(
        "CK-3083ES a CK-7082E master len číta. Žiadne ich nastavenie pri štarte nezapisuje."
    )
    lines.append("")
    lines.extend(_em2rs_lines(em2rs))
    lines.append("")
    lines.extend(_gd20_lines(gd20))
    lines.append("")
    lines.append("YAML, ktoré Python neberie, takže zmena v ňom beh nezmení:")
    lines.append("- em2rs_556.valve.pressure_interlock")
    lines.append("- em2rs_556.safety.scaling_confirmed a em2rs_556.manual.max_steps")
    lines.append("- em2rs_556.valve.full_travel_revolutions; beh berie full_travel_steps")
    lines.append("- em2rs_556.valve.min_position_percent a max_position_percent; beh berie kroky")
    lines.append("- em2rs_556.motion.acceleration a motion.deceleration; Path0 berie startup_check")
    lines.append("- invt_gd20.pid_defaults; P09.04, P09.05 a P09.06 master pri štarte nezapisuje")
    lines.append("- invt_gd20.commands.pid_feedback_command; spätná väzba PID ide z AI2 meniča")
    return "\n".join(lines)


def runtime_sheet(journal=None):

    text = _journal() if journal is None else journal
    lines = ["## Čo program práve hlási", ""]

    if text is None:
        lines.append("Journal mastera sa nepodarilo prečítať. Živý stav nepouži a povedz to.")
        return "\n".join(lines)

    gd20 = None
    em2rs = None

    for line in text.splitlines():
        found = _GD20_POLL.search(line)
        if found:
            gd20 = found
        found = _EM2RS_POLL.search(line)
        if found:
            em2rs = found

    if gd20 is None and em2rs is None:
        lines.append("Posledná vzorka meniča ani budiča v journale nie je.")
    if gd20 is not None:
        lines.append(_gd20_sample(gd20))
    if em2rs is not None:
        lines.append(_em2rs_sample(em2rs))

    setup = _setup_lines(text)
    lines.append("")

    if setup:
        lines.append("Zápis pri štarte mastera, len kde sa hodnota líšila:")
        lines.extend(f"- {item}" for item in setup)
    else:
        lines.append(
            "Riadky zo štartového zápisu v journale nie sú. "
            "Platí posledné porovnanie za behu vyššie, ak tam je."
        )

    return "\n".join(lines)


def _load(root, name):

    return yaml.safe_load((root / name).read_text(encoding="utf-8")) or {}


def _comma(value):

    text = str(value)

    if re.fullmatch(r"-?\d+\.\d+", text):
        text = text.rstrip("0").rstrip(".")
        return text.replace(".", ",")

    return text


def _scaled(word, scale):

    try:
        number = int(word) * float(scale)
    except (TypeError, ValueError):
        return None

    return _comma(f"{number:.1f}")


def _em2rs_lines(cfg):

    parameters = (cfg.get("startup_check") or {}).get("parameters") or {}
    registers = (cfg.get("modbus") or {}).get("registers") or {}
    lines = [
        "Budič EM2RS-556. Pri štarte mastera sa raz zapíše expected, ktoré sa od budiča líši. "
        "V ďalších cykloch sa tie isté hodnoty len čítajú. Do EEPROM sa to neukladá a "
        "spúšťací register pohybu sa pri tomto zápise nezapisuje.",
    ]

    for name, spec in parameters.items():
        if not isinstance(spec, dict):
            continue

        label = spec.get("parameter") or name
        expected = spec.get("expected")
        register = registers.get(spec.get("register")) or {}
        scale = register.get("scale")
        lines.append(f"- {_em2rs_item(name, label, expected, scale)}")

    return lines


def _em2rs_item(name, label, expected, scale):

    if name == "peak_current" and scale is not None:
        amps = _scaled(expected, scale)
        return f"{label} = {amps} A (slovo {expected})"

    if name == "path0_mode" and expected == 1:
        return f"{label} = absolútna poloha (slovo {expected})"

    unit = {
        "pulse_per_revolution": "pulzov na otáčku",
        "path0_speed": "otáčok za minútu",
        "path0_acceleration": "zrýchlenie",
        "path0_deceleration": "spomalenie",
        "path0_pause_time": "pauza po pohybe",
    }.get(name, "")
    suffix = f" {unit}" if unit else ""
    return f"{label} = {expected}{suffix}"


def _gd20_lines(cfg):

    setup = cfg.get("setup") or {}
    parameters = cfg.get("parameters") or {}
    written = [str(key) for key in (setup.get("parameters") or [])]
    stop_only = {str(key) for key in (setup.get("stop_only") or [])}
    lines = [
        "Menič INVT GD20. Pri štarte mastera sa zapíše required_value len u parametrov "
        "v setup.parameters, a len keď sa od meniča líši. Ostatné required_value "
        "master nečíta ani nezapisuje.",
    ]

    for key in written:
        spec = parameters.get(key) or {}
        label = spec.get("parameter") or key
        value = spec.get("required_value")
        when = "len keď menič stojí" if key in stop_only else "aj keď menič beží"
        lines.append(f"- {label} = {value}, {when}. {_gd20_meaning(label, value)}")

    for key, spec in parameters.items():
        if key in written or not isinstance(spec, dict) or "required_value" not in spec:
            continue

        label = spec.get("parameter") or key
        lines.append(
            f"- {label} required_value {spec['required_value']} master nezapisuje ani nečíta. "
            "Je to len očakávanie pre diagnostiku."
        )

    return lines


def _gd20_meaning(label, value):

    if label == "P00.01" and value == 2:
        return "Príkaz chodu ide z komunikácie."

    if label == "P01.21" and value == 0:
        return "Automatický reštart po výpadku je vypnutý."

    if label == "P05.04" and value == 6:
        return "S4 je voľný dobeh."

    if label == "P05.10" and value == 8:
        return "S4 má obrátenú logiku, S1 až S3 priamu."

    return ""


def _journal():

    try:
        live = subprocess.run(
            ["journalctl", "-u", "iot-master", "-n", "80", "-o", "cat", "--no-pager"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        setup = subprocess.run(
            ["journalctl", "-u", "iot-master", "--since", "7 days ago", "-o", "cat", "--no-pager", "-g", "setup "],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if live.returncode != 0 and setup.returncode != 0:
        return None

    return f"{live.stdout}\n{setup.stdout}"


def _gd20_sample(found):

    ts, freq, fset, sp, fb, ai2, fault, ext, status, run = found.groups()
    motion = "beží" if run == "1" else "stojí" if run == "0" else f"run {run}"
    state = _GD20_STATUS.get(status, f"stav {status}")
    stop = "aktívny" if ext == "True" else "nie je aktívny" if ext == "False" else ext
    return (
        f"Menič, vzorka {ts}: {motion}, {state}, frekvencia {_comma(freq)} Hz, "
        f"žiadaná frekvencia {_comma(fset)} Hz, PID žiadaná {_comma(sp)} kPa, "
        f"spätná väzba {_comma(fb)} kPa, AI2 {_comma(ai2)} kPa, "
        f"porucha {fault}, externý stop S4 {stop}."
    )


def _em2rs_sample(found):

    ts, status, pr0, pr5, mode, pos, speed, acc, dec, pause, gd20 = found.groups()
    state = _EM2RS_STATUS.get(status, status)
    current = f"{pr5} (0,8 A)" if pr5 == "8/8" else pr5
    band, _, error = gd20.partition("/")
    band_text = "v pásme" if band == "stable" else "mimo pásma" if band == "no" else band
    error_text = "odchýlka nie je známa" if error in ("", "-") else f"odchýlka {_comma(error)} kPa"
    return (
        f"Budič, vzorka {ts}: {state}. Pr0.00 {pr0}, Pr5.00 {current}, režim {mode}, "
        f"poloha {pos} krokov, "
        f"rýchlosť {speed}, zrýchlenie {acc}, spomalenie {dec}, pauza {pause}. "
        f"Menič pre dolaďovanie ventilu je {band_text}, {error_text}."
    )


def _setup_lines(text):

    names = _setup_names()
    last = {}

    for line in text.splitlines():
        found = _SETUP.search(line)
        if not found:
            continue

        device, name, rest = found.groups()
        rest = _HEX.sub("", rest).strip()
        last[(device, name)] = _setup_sentence(names.get((device, name), name), rest)

    return list(last.values())


def _setup_names():

    em2rs = _load(ROOT, EM2RS).get("em2rs_556") or {}
    parameters = (em2rs.get("startup_check") or {}).get("parameters") or {}
    names = {}

    for key, spec in parameters.items():
        if isinstance(spec, dict) and spec.get("parameter"):
            names[("EM2RS", key)] = spec["parameter"]

    return names


def _setup_sentence(label, rest):

    same = re.fullmatch(r"(\S+) == (\S+)", rest)
    if same:
        return f"{label}: sedí, hodnota {same.group(1)}"

    failed = re.fullmatch(r"(\S+) -> (\S+) WRITE_FAILED", rest)
    if failed:
        return f"{label}: zápis z {failed.group(1)} na {failed.group(2)} zlyhal"

    wrote = re.fullmatch(r"(\S+) -> (\S+)", rest)
    if wrote:
        return f"{label}: pri štarte zapísané z {wrote.group(1)} na {wrote.group(2)}"

    checked = re.fullmatch(r"read-back (\S+) != (\S+)", rest)
    if checked:
        return f"{label}: po zápise je {checked.group(1)}, očakávané {checked.group(2)}"

    if "deferred until STOP" in rest:
        return f"{label}: zápis odložený, kým menič stojí"

    if rest == "read failed":
        return f"{label}: čítanie pri štarte zlyhalo"

    if rest.startswith("write failed"):
        return f"{label}: zápis pri štarte zlyhal"

    if rest.startswith("skipped"):
        return f"{label}: vynechané"

    return f"{label}: {rest}"
