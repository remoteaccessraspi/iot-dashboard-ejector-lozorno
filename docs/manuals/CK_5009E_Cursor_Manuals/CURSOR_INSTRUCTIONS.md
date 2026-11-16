# Pokyny pre Cursor — CK-5009E

## Záväzné pravidlá
1. Pred úpravou prečítať všetky `.md` v tomto adresári a identifikovať existujúci Modbus poller, konfiguráciu, DB a HMI v `iot_dashboard`.
2. CK-5009E = **8DO NPN MOSFET**. Neimplementovať DI, analógové vstupy ani mechanické relé.
3. Použiť FC01 pre readback, FC05 pre jednotlivý zápis a FC0F pre hromadný zápis; adresy coil 0–7.
4. Štandardne `writes_enabled: false`. Zápisy povoliť až po explicitnom potvrdení používateľa a identifikácii bezpečnej záťaže.
5. Konfigurácia TCP IP je povinná a musí pochádzať z merania/konfigurácie zariadenia. Nevymýšľať továrenskú IP ani register nastavenia siete.
6. Prispôsobiť sa existujúcemu 5-sekundovému cyklu, nevytvárať druhý súbežný poller bez dôvodu.
7. V HMI odlíšiť `commanded_state`, `readback_state`, `communication_ok` a `last_seen`.
8. Chyba komunikácie => `unknown/stale`, nie falošné OFF; nevyvolávať automatický zápis.
9. Pred akoukoľvek zmenou programu vypracovať diff/plán, testovať na mock Modbus serveri, potom žiadať schválenie nasadenia.
10. Zaznamenávať audit zápisov (čas, používateľ, kanál, požadovaný stav, výsledok).

## Odporúčané zadanie
> Analyzuj existujúci projekt a podľa `docs/CK_5009E/` navrhni integráciu 8 DO modulu. Najprv priprav read-only driver, konfiguráciu a unit testy. Nevykonávaj zápisy na fyzický modul. Vypíš nejasnosti v dokumentácii a čakaj na potvrdenie.

## Nejasnosti originálu
- Str. 8 uvádza aj 16 DI a 16 DO v generickej tabuľke: **neplatí ako potvrdená kapacita CK-5009E**.
- Str. 5 obsahuje nesúvisiaci text CK-5162R.
- Str. 7 obsahuje obrázky CK-3168E; z nich nemožno prevziať default IP.
- Nie je uvedený detailný mechanizmus konfigurácie IP, ani garantovaný stav výstupov pri výpadku spojenia.
