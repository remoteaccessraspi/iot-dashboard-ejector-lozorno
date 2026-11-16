# Zadanie pre Cursor: OpenAI API Costs monitoring na Raspberry Pi

## Cieľ
Implementovať do existujúceho Python/FastAPI HMI na každom Raspberry Pi **nezávislé monitorovanie nákladov OpenAI API v USD**, bez centrálneho servera a bez sledovania predplateného zostatku. OpenAI organizácia používa automatické dobíjanie kreditu.

Každé RPi zobrazuje **vlastné náklady** (dnes UTC, aktuálny kalendárny mesiac UTC, celkom od definovaného začiatku sledovania) podľa vlastného OpenAI `project_id`. Voliteľne môže zobraziť aj celkovú spotrebu organizácie, ale tá nie je primárnou požiadavkou.

## Overený základ
- Úspešne otestovaný `GET https://api.openai.com/v1/organization/costs` s Admin API key.
- Funguje `bucket_width=1d` aj `group_by=project_id`.
- Príklad existujúceho projektu: `proj_dJCZWyonLGYmH6qbiM7w5IGt` (identifikátor je príklad, nepredpokladať, že patrí konkrétnej inštalácii).
- Overená spotreba v testovacom 30-dňovom intervale: 0.0209696 USD; ide o test, nie o konfiguračnú konštantu.
- API používa unixové UTC timestampy, odpoveď obsahuje `data[].results[].amount.value`, `has_more`, `next_page`.

## Architektúra
Každé RPi:
1. Existujúca aplikácia HMI/FastAPI.
2. Samostatný asynchrónny/periodický billing worker (nie v 5-sekundovom meracom cykle), polling napr. každých 5–15 minút.
3. HTTPS dotaz priamo na OpenAI Costs API.
4. Lokálna cache výsledkov a REST endpoint pre HMI.
5. Žiadna komunikácia medzi RPi; žiadny centrálny server.

## Bezpečnosť – povinné
- Costs API vyžaduje **organizational Admin API key**, ktorý má široké oprávnenia. Nezamieňať s bežným projektovým API kľúčom.
- Kľúč **nikdy** neposielať do frontendu, JavaScriptu, REST odpovede, logov ani Git repozitára.
- Na RPi čítať z environment variable `OPENAI_ADMIN_KEY` alebo z root-owned secret súboru mimo repozitára s prísnymi právami; prístup len servisnému účtu.
- Zdokumentovať bezpečnostné riziko opakovania Admin key na viacerých RPi; overiť, či sú v účte dostupné obmedzené oprávnenia pre read-only billing. Ak nie, nepredstierať, že ide o read-only token.
- Timeout, retry s exponenciálnym backoff, rešpektovanie HTTP 429, bez logovania autorizačných hlavičiek.
- Ak sa API nepodarí načítať, HMI ukáže poslednú známu hodnotu a označenie `stale` s časom poslednej aktualizácie.

## Konfigurácia
Prispôsobiť existujúcej štruktúre `config/settings.yaml` (bez tajomstiev):

```yaml
openai_billing:
  enabled: true
  project_id: "REPLACE_WITH_THIS_RPI_PROJECT_ID"
  poll_interval_seconds: 600
  tracking_start_utc: "2026-11-01T00:00:00Z"
  currency: "USD"
```

Každé RPi musí mať **samostatný OpenAI Project a samostatný projektový API kľúč pre generovanie**, aby bolo možné náklady jednoznačne priradiť. Všetky projekty sú v jednej organizácii a používajú spoločné účtovanie. Admin key pre Costs API je samostatná poverovacia informácia.

## API dotaz
Príklad:

`GET /v1/organization/costs?start_time=<unix>&end_time=<unix>&bucket_width=1d&group_by=project_id&limit=31`

- `start_time` a `end_time` počítať v UTC; koniec je exkluzívny.
- Implementovať stránkovanie `has_more` / `next_page` a primerané delenie dlhých intervalov.
- Sčítať `amount.value` len pre `project_id` tejto inštalácie.
- Nepoužívať binárny float pre účtovné súčty: `Decimal(str(value))`.
- Ošetriť prázdne `results`, nulové náklady, chýbajúci `project_id`, výpadky siete a oneskorené účtovanie.
- **Pozor:** výsledky Costs API môžu byť oneskorené alebo spätne upravené. Posledné dni periodicky znovu načítavať; ak sa uchováva lokálna DB, použiť upsert (nie pripočítanie opakovaných dotazov).
- Pri väčšej histórii odporúčané lokálne per-day cache/DB, plus pravidelná rekonciliácia. Nezamieňať „celkom od tracking_start_utc“ s celou historickou spotrebou organizácie.

## Výstup REST endpointu
Navrhované `GET /api/openai/costs` (uprav podľa existujúcich konvencií):

```json
{
  "project_id": "proj_example",
  "currency": "USD",
  "today_usd": "0.000000",
  "month_usd": "0.000000",
  "total_since_tracking_start_usd": "0.000000",
  "tracking_start_utc": "2026-11-01T00:00:00Z",
  "last_successful_update_utc": null,
  "stale": true,
  "status": "not_initialized"
}
```

Hodnoty sú reťazce, aby sa nestratila presnosť desatinných miest. HMI môže zobrazovať USD so 4–6 desatinnými miestami pri nízkych sumách.

## HMI
- Kompaktná karta „OpenAI API – náklady“.
- Tri čísla: **Dnes**, **Tento mesiac**, **Celkom od začiatku sledovania**.
- Čas poslednej úspešnej aktualizácie, indikácia `stale/error`.
- Voliteľne denný graf za 7/30 dní.
- Bez zobrazenia kreditu, expirácií, nákupov či auto-recharge nastavení.

## Integrácia do existujúceho projektu
Cursor má najprv preskúmať skutočnú štruktúru repozitára, existujúci FastAPI app, konfiguráciu, DB, frontend a spôsob spúšťania služieb. Nemá vytvárať paralelnú aplikáciu, ak sa dá rozšíriť existujúca. Zachovať 5-sekundový polling Modbus a nezávislosť regulačných slučiek od API/internetu.

## Akceptačné testy
1. Porovnať náklady projektu s OpenAI Costs API pre rovnaké UTC obdobie.
2. Otestovať dva odlišné `project_id`: každé RPi ukazuje iba svoju spotrebu.
3. Otestovať nulovú spotrebu, HTTP 401/403/429/5xx, timeout, chýbajúci kľúč.
4. Otestovať stránkovanie a spätnú zmenu nákladov bez dvojitého započítania.
5. Overiť, že žiadny secret sa nedostane do browsera, logov ani Git.
6. Overiť, že výpadok OpenAI neovplyvní Modbus, reguláciu, databázu meraní ani HMI ako celok.

## Požadovaný postup Cursoru
1. Najprv vypísať návrh minimálnych zmien a dotknuté súbory.
2. Identifikovať existujúce konvencie projektu a možné konflikty.
3. Až potom implementovať backend worker, endpoint a HMI kartu.
4. Dodať krátky návod na nastavenie kľúča, projektového ID, systemd a testovanie.
5. Nepoužívať vymyslené API endpointy pre zostatok kreditu.
