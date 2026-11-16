# CK-5009E — Cursor technický manuál

Zdroj: Chengkong Electronics, *CK-5009E Ethernet Cascade Switch Output Specification*, Vr1.0, 12 strán. Poznámky odkazujú na čísla strán originálneho PDF.

## Identifikácia
- 8 digitálnych výstupov DO0–DO7, NPN MOSFET, **nie bezpotenciálové relé** (str. 3, 5–6).
- Menovitá zaťažiteľnosť výstupu podľa výrobcu: **1,25 A**; podmienky tejto hodnoty manuál nerozvádza (str. 5).
- Modbus TCP (Ethernet) a Modbus RTU (RS485) (str. 3, 8).
- Napájanie DC 9–30 V; str. 3 súčasne uvádza 12/24 V ako typické napájanie (str. 3, 9).
- DIN35; rozmery približne 110 × 95 × 30 mm (str. 10).

## Súbory
- `MODBUS_REGISTERS.md`: presné adresovanie a rozdiel medzi 8/16 kanálmi
- `VARIABLES.md`: pomenovanie a model dát
- `CONFIGURATION.md`: TCP/RTU a neoverené nastavenia
- `WIRING_AND_SAFETY.md`: svorky a bezpečnosť
- `TESTING.md`: postup validácie bez neúmyselného spínania
- `CURSOR_INSTRUCTIONS.md`: pravidlá implementácie

**Kritické:** Nezamieňať CK-5009E za CK-5162E alebo CK-TP5163. Tento modul nemá zdokumentované digitálne vstupy. Žiadny zápis na živý hardvér bez explicitného súhlasu používateľa.
