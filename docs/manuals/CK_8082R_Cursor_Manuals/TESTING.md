# Testovanie bez zápisu
Zdrojové údaje: Vr1.0, str. 8–9. Nasledujúci postup je odporúčanie integrácie.

1. Overiť štítok, rozsah a kalibráciu (mA/V), napájanie a RS485 vodiče.
2. Zistiť port adaptéra, nastaviť 9600 8N1 a skutočné slave ID (mechanický volič môže prepísať softvérovú adresu).
3. Čítať FC03 od adresy 96, počet 8; pri neúspechu skúsiť iba diagnostiku spojenia, nie zápisy.
4. Každý register interpretovať ako `int16`, deliť 1000, označiť správnou jednotkou.
5. Skontrolovať nulový/referenčný signál a záporné hodnoty; porovnať s externým meradlom.
6. Pri odpojení RS485 overiť timeout a `quality=timeout`; poslednú platnú hodnotu nesprístupniť ako aktuálne meranie.
7. Zmerať spoľahlivosť počas niekoľkých desiatok poll cyklov. Polling 5 s je návrh podľa existujúceho systému, nie požiadavka výrobcu.

Očakávané testy dekódera: `0x418D -> 16.781`; `0x13E1 -> 5.089`; `0xF249 -> -3.511`; `0xF6D7 -> -2.345`.
