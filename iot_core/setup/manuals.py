import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANUALS = ROOT / "docs/manuals"

DEVICES = (
    "INVT_GD20_EU_Cursor_Manuals",
    "EM2RS_556_Cursor_Manuals",
    "CK_7082E_Cursor_Manuals",
    "CK_3043ES_3083ES_Cursor_Manuals",
)

SKIP = {"CURSOR_INSTRUCTIONS.md"}
WORD = re.compile(r"[a-z0-9]{3,}")
REGISTER = re.compile(r"0x[0-9a-fA-F]+\b")
FUNCTION = re.compile(r"\bFC0\d\b")
COMMAND = re.compile(r"voľný dobeh|volny dobeh|jog|reset poruchy", re.I)
STOP = {
    "ako", "aby", "ale", "alebo", "bez", "bol", "bude", "cize", "iba", "ked",
    "kde", "kto", "kym", "nie", "ona", "ono", "pre", "pri", "pro", "som",
    "tak", "ten", "toto", "tato", "the", "and",
}


def fold(text):

    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def files():

    found = []

    for device in DEVICES:
        folder = MANUALS / device
        found.extend(path for path in sorted(folder.glob("*.md")) if path.name not in SKIP)

    return found


def sanitize(text):

    """Adresy registrov a príkazy chodu do podkladu pre agenta nepatria."""

    kept = [line for line in text.splitlines() if not COMMAND.search(line)]
    return FUNCTION.sub("funkcia", REGISTER.sub("register", "\n".join(kept)))


def excerpts(question, limit=3, max_chars=9000):

    """Najviac `limit` manuálov, ktorých slová sa kryjú s otázkou."""

    asked = set(WORD.findall(fold(question or ""))) - STOP

    if not asked:
        return ""

    scored = []

    for path in files():
        text = sanitize(path.read_text(encoding="utf-8"))
        score = len(asked & set(WORD.findall(fold(text))))

        if score:
            scored.append((score, path, text))

    if not scored:
        return ""

    scored.sort(key=lambda item: (-item[0], item[1].name))
    best = max(scored, key=lambda item: item[0])[1].parent
    same = [item for item in scored if item[1].parent == best]
    other = [item for item in scored if item[1].parent != best]
    scored = same + other
    chosen = []
    used = 0

    for _score, path, text in scored[:limit]:
        room = max_chars - used

        if room <= 0:
            break

        body = text if len(text) <= room else text[:room] + "\n…\n"
        chosen.append(f"### {path.parent.name}/{path.name}\n\n{body}")
        used += len(body)

    if not chosen:
        return ""

    return (
        "Podklady z manuálov zariadení, ktoré sú na tejto zbernici. "
        "Odpovedaj len z nich a z tabuľky Zapojenie. Čo v nich nie je, povedz a nevymýšľaj, "
        "najmä nie sled tlačidiel na paneli.\n"
        "Vysvetlenie nie je návrh, takže changes nechaj prázdne.\n"
        "Parameter meniča Pxx.yy uviesť smieš. Adresu registra a funkčný kód nie.\n"
        "Svorky tejto inštalácie ber z tabuľky Zapojenie, nie prepočtom z všeobecného manuálu.\n\n"
        + "\n\n".join(chosen)
    )
