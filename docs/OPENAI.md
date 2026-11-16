# OpenAI API — pripojenie z projektov

Tento kľúč je **OpenAI Platform** (`api.openai.com`), predplatené kredity na organizácii.  
**Nie** je to ChatGPT Plus, **nie** Cursor predplatné. Tie do Python skriptov nejdú.

Platí pre `iot_dashboard`, `images`, `pdf-translate`, `scraper` aj ďalšie lokálne projekty.

---

## Prístupové práva

| Čo | Stav |
|----|------|
| Typ kľúča | `sk-proj-…` (OpenAI **project** key) |
| Kam siahne | celý OpenAI projekt / organizácia, ktorá kľúč vydala |
| Chat Completions | áno (`gpt-4.1-mini`, preklad, vision, …) |
| Images Edit | áno (`gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`) |
| Zostatok | spoločný — všetky projekty ťahajú **rovnaké** kredity |
| ChatGPT web / Cursor | **nemajú** tento kľúč; pri prázdnom zostatku API padne aj keď Plus ešte ide |

Kľúč vie volať API, na ktoré má projekt v [platform.openai.com](https://platform.openai.com) povolenie. Obmedziť práva (len chat, bez Images, IP allowlist) ide v:

[platform.openai.com/api-keys](https://platform.openai.com/api-keys)

Kredity a fakturácia:

[platform.openai.com/settings/organization/billing](https://platform.openai.com/settings/organization/billing)

Chyba `credit_balance_exhausted` / 429 = prázdny zostatok, nie zlý kľúč.

---

## Prístup (kľúč)

V tomto projekte je kľúč v `config/secrets.yaml`, sekcia `openai`, kľúč `api_key`. Súbor nie je v gite. Vzor bez hodnoty je `config/secrets.yaml.example`. Čítanie ide cez `load_openai_secrets()` v `iot_core/core/config.py`.

Ostatné lokálne projekty majú vlastnú kópiu v `.env` (`OPENAI_API_KEY`). Tento markdown kľúč neobsahuje.

| Súbor | Účel |
|-------|------|
| `config/secrets.yaml` | kľúč tohto dashboardu, `openai.api_key` |
| `pdf-translate/.env` | kópia pre preklad |
| `scraper/.env` | kópia pre scraper |
| `images/.env` | voliteľné; ak chýba, `images` číta `pdf-translate/.env` |

Model na úpravu obrázkov v projekte `images` je `gpt-image-2` (`OPENAI_IMAGE_MODEL`). Do `secrets.yaml` nepatrí, nie je to prístupový údaj.

---

## Použitie v tomto projekte

Balík `openai`. Kľúč ber z `secrets.yaml`, nie z prostredia a nie z tohto súboru.

```python
from openai import OpenAI

from iot_core.core.config import load_openai_secrets

api_key = load_openai_secrets().get("api_key")
if not api_key:
    raise RuntimeError("Chýba openai.api_key v config/secrets.yaml")

client = OpenAI(api_key=api_key)
```

Súbor má práva len pre vlastníka:

```bash
chmod 600 config/secrets.yaml
```

Pi míňa rovnaké Platform kredity ako ostatné lokálne projekty. Samostatný kľúč s limitom patrí znova do `openai.api_key`.

---

## Príklady volaní

Text (ako `pdf-translate`):

```python
response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": "Ahoj"}],
)
print(response.choices[0].message.content)
```

Úprava obrázka (ako `images`, `images.edit`):

```python
# pozri images/openai_wireframe.py → edit_image()
# gpt-image-2 neberie input_fidelity; timeout ~300 s
```

Hotový klient v tomto workspace: `images/openai_wireframe.py` → `create_openai_client()`.

---

## Náklady na karte Setup

Karta Setup, pod oknom Recent changes, ukazuje USD z Costs API pre `project_id`
tohto Pi: dnes, tento kalendárny mesiac a celkom od `tracking_start_utc`.
Hodnoty sú v UTC. Zostatok kreditu sa nečíta.

Nastavenie v `config/common.yaml`, blok `openai_billing`:

- `project_id` je projekt tohto Raspberry Pi (`proj_…`). Každé Pi má vlastný.
- `tracking_start_utc` je začiatok súčtu, nie celá história organizácie.
- `poll_interval_seconds` je 600. Worker beží v `iot-dashboard`, mimo Modbusu.

Admin key nie je projektový `api_key`. Má široké práva organizácie. Daj ho
buď do prostredia `OPENAI_ADMIN_KEY`, alebo do `openai.admin_key` v
`config/secrets.yaml` (`chmod 600`). Do prehliadača, logu ani gitu nepatrí.

```bash
sudo systemctl restart iot-dashboard
```

Nová systemd jednotka netreba. Overenie: v servise otvor Setup. Tri sumy musia
sedieť s `GET /v1/organization/costs` pre rovnaký UTC rozsah a `project_id`.
Keď API neodpovie, ostanú posledné čísla a riadok povie, že sú stale. Modbus
a regulácia idú ďalej.

## Čo nesmieš

- Kľúč do `README`, `docs/OPENAI.md`, `.env.example`, verejného gitu, chatu alebo fotky obrazovky.
- Použiť ChatGPT session / Cursor token ako `openai.api_key`.
- Čakať, že Plus predplatné doplní Platform kredit.
- Dávať kľúč na HMI alebo do YAML, ktoré ide na GitHub. `config/secrets.yaml` v gite nie je. `config/common.yaml` a `config/devices/` áno.

Existujúci problém: `pdf-translate/.env.example` obsahuje reálny kľúč. Pred pushom ho vymeň za prázdne `OPENAI_API_KEY=` a kľúč v Platform rotuj, ak mohol uniknúť.
