# Cursor — pravidlá integrácie CK-7082E do iot_dashboard

Zdroj hardvérových údajov: Chengkong CK-7082E Vr1.1. Tieto pokyny sú aplikačné pravidlá.

1. Najprv prečítaj všetky `.md` v tomto adresári a existujúcu architektúru projektu; zachovaj existujúce názvoslovie, konfiguráciu, Modbus scheduler, databázovú vrstvu a API.
2. Zariadenie je **8-kanálový analógový VSTUP**, nie výstup. Pre meranie použi iba FC03, offset 96–103, jeden blok 8 registrov.
3. Každý register dekóduj `signed int16 / 1000`; jednotku (`mA` alebo `V`) nastav explicitne podľa overeného hardvérového variantu.
4. Fyzikálne veličiny (tlak, prietok, hladina) škáluj až samostatnou vrstvou s kalibráciou konkrétneho snímača. Nikdy nezamieňaj raw mA/V s kPa alebo °C.
5. IP, port, unit ID, timeout a mapovanie kanálov udržuj v existujúcej projektovej konfigurácii; predvolenú IP z tohto PDF nepoznáme.
6. Integruj do existujúceho 5 s pollingu bez paralelných kolidujúcich požiadaviek na rovnakého klienta.
7. Každé meranie nesie timestamp, kvalitu, chybový stav; pri chybe komunikácie nevytváraj falošné nové meranie.
8. Zápis do registrov, zmena IP alebo rozsahu bez výrobcom potvrdeného postupu sú zakázané.
9. Pred úpravami kódu vypíš plán, dotknuté súbory a testy. Najprv priprav read-only integráciu a unit testy signed konverzie.
10. Nezamieňaj CK-7082E (16-bit) s CK-8082E (24-bit) ani CK-7082R (bez Ethernetu).

## Požadované testy
- `0x0000 -> 0.000`; `0x1168 -> 4.456`; `0xF6D7 -> -2.345`; `0xFFFF -> -0.001`.
- Overenie správneho bloku 8 registrov; Modbus timeout; exception; nesprávny počet registrov; výpadok senzora.
