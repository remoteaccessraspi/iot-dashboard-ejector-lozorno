# CK-TP5163 — dokumentácia pre Cursor

Zdroj: *CK-TP5163 Specifications Vr1.1*, Shenzhen Chengkong Electronics, 11 strán. Táto dokumentácia sa týka **výhradne CK-TP5163**, nie CK-TP5162/CK-TP5016.

## Zariadenie
- 16 opticky oddelených digitálnych vstupov DI0–DI15.
- 12 reléových výstupov DO0–DO11.
- Modbus TCP server; výrobcom uvádzaná predvolená adresa `192.168.1.30`, port `502` (s. 7).
- Napájanie 10–30 V DC, nominálne 24 V DC; príkon 2 W (s. 2, 9).
- Dva RJ45 porty s možnosťou kaskádovania (s. 6).

## Súbory
1. `MODBUS_REGISTERS.md` — adresy a funkčné kódy.
2. `VARIABLES.md` — dátový model, názvoslovie a mapovanie.
3. `CONFIGURATION.md` — sieť, timeout a ukladanie nastavení.
4. `WIRING_AND_SAFETY.md` — fyzické svorky a limity.
5. `CURSOR_INSTRUCTIONS.md` — záväzné pravidlá pre Cursor.

## Pozor na neistoty zdroja
- Na s. 9 je v tabuľke omylom uvedené `EtherCAT`, hoci titul, prehľad a komunikačná kapitola opakovane uvádzajú **Modbus TCP**. Používaj Modbus TCP; rozpor eviduj.
- Manuál neuvádza register na nastavenie IP, masky, gateway ani explicitné adresy predvolených stavov DO. **Nevymýšľaj ich.**
- Príklady rámcov na s. 8 sú generické pre 8-kanálový modul; pre CK-TP5163 používaj mapu 16 DI/12 DO.
- V manuáli sú adresy uvedené ako HEX offsety; v knižnici `pymodbus` ich používaj ako nulovo indexované adresy, nie ako 3xxxx/4xxxx referencie.
