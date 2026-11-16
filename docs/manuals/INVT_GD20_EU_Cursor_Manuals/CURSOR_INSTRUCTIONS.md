# Inštrukcie pre Cursor — INVT GD20-EU

1. Pred implementáciou prečítaj všetky `.md` v tomto adresári a existujúci kód projektu.
2. Používaj výrobcom dokumentované adresy; neodvodzuj neoverené registre zo susedných modelov.
3. Zdroj pravdy: `docs/GD20-EU VFD Manual _V1.9.pdf` a `MODBUS_REGISTERS.md`. Pri rozpore s meničom zastav a vypýtaj si potvrdenie.
4. Zachovaj existujúcu Modbus RTU zbernicu a spoločný poll, nevytváraj druhého súbežného mastera.
5. Master pri štarte zapisuje len P01.21, P05.10 a, keď menič stojí, P00.01 a P05.04. Ďalšie parametre pri štarte nezapisuj.
6. `0x2002` je 0–100,0 %. Program ho plní zo `gd20_setpoint_kpa` rozsahom 0–1500 kPa. `0x2001` je iný register a program ho nepoužíva.
7. RUN zapisuje `0x2000 = 1`, STOP zapisuje `0x2000 = 5`. Reset poruchy, chod vzad a voľný dobeh cez komunikáciu program nezapisuje.
8. Nezamieňaj `0x2002` s tlakom v kPa ani `0x3001` so zápisom frekvencie `0x2001`.
9. Nenahrádzaj fyzické ochrany čerpadla softvérom Raspberry Pi.
10. Pred zmenami vytvor plán, diff, rollback a testovací protokol. Neprepisuj DB schému bez schválenia.
