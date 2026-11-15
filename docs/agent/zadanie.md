# Zadanie — karta Setup s AI agentom

Stav: implementované 15. novembra 2026 (`iot_core/setup/`, `/setup`).

## Účel

Kritériá v YAML sú pre zákazníka nezrozumiteľné. Karta Setup mu dovolí povedať po slovensky, čo chce zmeniť („štart generátora až od 85 °C“, „pridaj mail technika“). AI agent vetu preloží na zmenu povoleného kľúča a ukáže ju. Súbor zapíše až Python po kliknutí na Súhlas.

Agent sa riadi manuálom `docs/agent/pravidla.md`. Toto zadanie popisuje kartu, backend a zápis okolo neho.

## Kto a kde

- Odkaz **Setup** v navigácii, za kartou ventilu. Vidno ho len pri otvorenom servise, rovnako ako karty zariadení.
- Stránka `/setup` bez servisnej relácie vráti to isté ako ostatné servisné stránky (`_service_page`).
- Všetky API karty (`/api/setup/*`) chcú servisnú reláciu (`_service_api`), inak 401.
- Každá akcia v karte predlžuje servisnú reláciu ako ostatné karty (`/api/hmi/activity`).

## Tok jednej požiadavky

1. Zákazník napíše vetu a odošle ju.
2. Backend zloží správy pre model:
   - systémová správa: celý `pravidla.md`
   - druhá systémová správa: aktuálne hodnoty všetkých povolených kľúčov priamo zo súborov na disku (nie z cache procesu) a stav meniča (beží / stojí)
   - história rozhovoru z tejto relácie
   - veta zákazníka
3. Model vráti JSON podľa schémy nižšie.
4. Backend návrh overí. Čo neprejde, z návrhu vypadne a karta povie prečo.
5. Karta ukáže odpoveď agenta a pod ňou kartičku návrhu: kľúč, stará hodnota, nová hodnota, prepočítané hrany, či treba reštart. Tlačidlá **Súhlas** a **Zrušiť**.
6. Po Súhlase backend overí znova a zapíše.
7. Karta ukáže výsledok a pri potrebe reštartu banner „Zmena čaká na reštart“.

Model nikdy nezapisuje a nevolá žiadny nástroj. Jeho výstup je len text a návrh.

## Výstup modelu

Structured Outputs (JSON schema, `strict`), aby sa návrh dal strojovo overiť:

```json
{
  "reply": "text pre zákazníka po slovensky",
  "understood": "veta zákazníka vlastnými slovami, alebo null",
  "question": true,
  "changes": [
    {"key": "channels.t3.ready_min", "old": 80, "new": 85}
  ]
}
```

- `question: true` znamená, že agent sa pýta a `changes` je prázdne.
- `key` je identifikátor zo zoznamu povolených kľúčov, nie cesta k súboru. Súbor k nemu priradí Python.
- Hrany a potrebu reštartu si Python počíta sám. Číslu od modelu v týchto veciach neverí.
- Jeden návrh môže meniť viac kľúčov naraz (stred aj hysteréza). Súhlas zapíše všetky alebo žiadny.

## Zoznam povolených kľúčov

Jediný zdroj pravdy je Python modul `iot_core/setup/keys.py`. Pre každý kľúč:

| Pole | Význam |
|------|--------|
| `key` | identifikátor, napr. `channels.t3.ready_min` |
| `file` | pevný súbor, napr. `config/devices/ck_3083es_8ch.yaml` |
| `path` | cesta v YAML toho súboru |
| `type` | int, float, bool, zoznam mailov, alebo číslo / `na` |
| `soft` | rozumný rozsah z `pravidla.md`; mimo neho chce druhé potvrdenie |
| `hard` | absolútna hranica; mimo nej sa návrh zamietne |
| `restart` | áno pre súbory zariadení a `common.yaml`, nie pre `emails.yaml` |

Prvá verzia obsahuje presne kľúče, ktoré `pravidla.md` označuje ako zapisovateľné:

- teploty: `start.hold_s`, `start.stop_hold_s`, `channels.t3/t6/t1.ready_min/ready_max/ready_hyst`, `channels.t6.ready_max_stable`
- kavitácia: `cavitation.enabled`, `min_kpa`, `confirm_s`, `frequency_limit_hz`
- `common.yaml`: `alarms.loop_low_ma`, `loop_high_ma`, `loop_max_age_s`, `ready_max_age_s`, `ready_max_gap_s`, `cavitation_max_age_s`, `cavitation_arm_lookback_s`, `comm_fail_cycles`, `hmi.service_idle_min`
- ventil: `valve.park_percent`, `valve.closed_stop_percent`
- `emails.yaml`: `recipients`

Väzby medzi kľúčmi, ktoré Python kontroluje po zložení návrhu so súčasným stavom:

- `stop_hold_s < hold_s`
- `ready_max_stable > ready_max`
- `loop_low_ma < loop_high_ma`
- hysteréza nie je záporná
- `closed_stop_percent` je číslo 0 až 100 alebo `na` bez ohľadu na veľkosť písmen
- `recipients` sú platné adresy a zoznam nie je prázdny

Test overí, že každý kľúč zo zoznamu v YAML existuje, nie je označený NEAKTÍVNE a `pravidla.md` ho spomína. Keď sa manuál a zoznam rozídu, test padne.

## Zápis

- Zámok súboru (`fcntl`), aby dva klienti nezapisovali naraz.
- Pred zápisom znova prečítať súbor. Keď stará hodnota nesedí s tým, čo videl zákazník, zápis sa zruší s hláškou „Súbor sa medzitým zmenil“.
- Zmena sa robí v texte, len hodnota na riadku daného kľúča. Komentáre, poradie a odsadenie ostanú. PyYAML `dump` sa nepoužije, lebo by zmazal komentáre NEAKTÍVNE.
- Po úprave sa starý aj nový text súboru načíta cez YAML. Musí sa zmeniť presne navrhnutý kľúč a nič iné. Inak sa nezapíše.
- Zápis cez dočasný súbor a `os.replace`, aby výpadok napájania nenechal polovičný YAML.
- Kópia pôvodného súboru do `var/setup-backup/` s časom v mene. Drží sa posledných 50.
- Záznam o zmene do `var/setup-changes.jsonl`: čas, veta zákazníka, kľúč, stará a nová hodnota, či bolo druhé potvrdenie.

Karta má zoznam posledných zmien s tlačidlom **Vrátiť**. Vrátenie ide tou istou cestou ako nový návrh, vrátane overenia a súhlasu.

## Reštart

Python vie z kľúča, či zmena potrebuje reštart `iot-master`, `iot-dashboard` a `iot-db-archive`. Karta drží banner, kým beží proces starší ako posledný zápis do súborov konfigurácie.

Tlačidlo **Reštartovať** v banneri je povolené len keď menič stojí. Backend stav overí znova tesne pred reštartom. Sudoers `systemd/sudoers-iot-ejector` už dovoľuje tieto reštarty bez hesla. Dashboard reštartuje sám seba posledný, odpojeným procesom, a stránka sa po návrate služby obnoví.

## Model a náklady

- Nový blok `setup_agent` v `config/common.yaml`: `enabled`, `model`, `timeout_s`, `max_output_tokens`, `daily_limit`.
- Predvolené: `gpt-4.1-mini`, 30 s, 800 tokenov, 100 požiadaviek denne.
- `monthly_budget_usd` (1 $) a ceny za milión tokenov. Pod rozhovorom je riadok: tokeny a USD dnes a za mesiac, zvyšok rozpočtu, otázky dnes. Po minutí rozpočtu agent do konca mesiaca neodpovedá.
- Skutočný zostatok kreditu OpenAI projektový kľúč prečítať nevie (403, chýba `api.usage.read`; zostatok vracia len prehliadač). Je aj spoločný s inými projektmi.
- História rozhovoru sa drží len v otvorenej stránke a zmaže sa pri jej opustení. Posiela sa posledných 10 výmen. Podvrhnutá história nič nezapíše, návrh aj tak prejde kontrolou v Pythone.
- Balík `openai` pribudne do `requirements.txt` s pevnou verziou.

## Chyby

Každá chyba končí slovenskou hláškou v karte a žiadnym zápisom.

| Situácia | Hláška |
|----------|--------|
| chýba `openai.api_key` | Agent nie je nastavený, chýba kľúč. |
| bez internetu, timeout | Agent je nedostupný. Skúste neskôr. |
| 401 | Kľúč OpenAI neplatí. |
| 429, `credit_balance_exhausted` | Kredit OpenAI je minutý. |
| denný limit | Dnešný limit požiadaviek je vyčerpaný. |
| neplatný JSON od modelu | Agent odpovedal nezrozumiteľne. Skúste vetu inak. |
| kľúč mimo zoznamu | ten kľúč z návrhu vypadne a karta to povie |

Karta bez agenta ostáva použiteľná: zoznam zmien a Vrátiť fungujú aj offline.

## Bezpečnosť

- Kľúč OpenAI sa číta len v backende a nikdy nejde do prehliadača ani do logu.
- Do modelu ide len `pravidla.md`, hodnoty povolených kľúčov, stav meniča a text zákazníka. Žiadne heslá, `secrets.yaml`, databáza ani registre.
- Model nevolí súbor. Cesta sa berie len zo zoznamu kľúčov.
- Veta zákazníka má najviac 1000 znakov.
- Odpoveď modelu sa v prehliadači vkladá ako text, nie HTML.

## Súbory na implementáciu

| Súbor | Čo |
|-------|-----|
| `iot_core/setup/keys.py` | zoznam kľúčov, rozsahy, väzby, výpočet hrán |
| `iot_core/setup/yaml_edit.py` | textová úprava hodnoty, overenie, atomický zápis, záloha |
| `iot_core/setup/agent.py` | zloženie správ, volanie OpenAI, kontrola schémy |
| `app.py` | `/setup`, `/api/setup/chat`, `/api/setup/apply`, `/api/setup/history`, `/api/setup/revert`, `/api/setup/restart` |
| `templates/setup.html`, `static/js/setup.js` | karta s dialógom a kartičkami návrhov |
| `templates/header.html` | odkaz Setup |
| `config/common.yaml` | blok `setup_agent` |
| `update.sh` | zastaví sa pred `git pull`, keď sú v `config/` lokálne zmeny |
| `tests/test_setup_*.py` | testy bez siete, OpenAI sa mockuje |

Po implementácii sa v `pravidla.md` zmaže veta „Kým ten krok v karte nie je…“ a README dostane sekciu Setup.

## Akceptačné scenáre

1. „Štart generátora od 85 °C“ dostane otázku, či stred alebo hranu. Žiadny návrh.
2. „Hysteréza generátora 2 stupne“ dá návrh so stredom, hysterézou a oboma hranami (štart od 82, stop pod 78).
3. „Spomaľ PID“ odmietne s vysvetlením, že PID beží v meniči.
4. „Zavri ventil“ odmietne, je to povel obsluhy, nie kritérium.
5. `hold_s` 900 s ukáže návrh s červeným druhým potvrdením.
6. `stop_hold_s` väčší ako `hold_s` Python zamietne aj keby ho model navrhol.
7. Ručná úprava súboru medzi návrhom a Súhlasom zruší zápis.
8. Po zápise ostanú v súbore všetky komentáre a `git diff` ukáže jeden zmenený riadok.
9. Bez internetu karta povie, že agent je nedostupný, a zoznam zmien funguje.
10. Vrátiť obnoví pôvodnú hodnotu a zapíše záznam.

## Rozhodnuté

1. **Reštart.** Tlačidlo **Reštartovať** v karte. Je povolené len keď menič stojí podľa čerstvej vzorky. Pri behu alebo bez vzorky je sivé s vysvetlením.
2. **Záznam zmien.** Súbor `var/setup-changes.jsonl` na SD, jeden riadok JSON na zmenu. Funguje aj bez databázy.
3. **Git.** Zmeny z karty sa necommitujú. `update.sh` pred `git pull` skontroluje `git status config/`, zmenené súbory vypíše a skončí bez pullu. Obsluha zmeny prenesie do repozitára alebo ich odloží.
4. **Model.** `gpt-4.1-mini`.
5. **Písanie.** Karta sa používa na kiosku s externou klávesnicou aj z počítača alebo telefónu cez sieť. Klávesnica na obrazovke netreba. Enter odošle vetu, Shift+Enter nový riadok. Po načítaní karty a po odpovedi agenta je kurzor v poli na písanie.
