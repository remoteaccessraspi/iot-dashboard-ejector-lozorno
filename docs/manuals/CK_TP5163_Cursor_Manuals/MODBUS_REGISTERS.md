# CK-TP5163 — Modbus TCP register map

Zdroj: výrobca Vr1.1, s. 7–8. Všetky adresy sú **zero-based offsety** (hex aj decimálne). FC = Modbus function code.

## Digitálne vstupy
| Premenná | FC | Adresa HEX | Adresa DEC | Operácia |
|---|---|---|---|---|
| DI0 | 02 | 0x0000 | 0 | čítanie bitu |
| DI1 | 02 | 0x0001 | 1 | čítanie bitu |
| DI2 | 02 | 0x0002 | 2 | čítanie bitu |
| DI3 | 02 | 0x0003 | 3 | čítanie bitu |
| DI4 | 02 | 0x0004 | 4 | čítanie bitu |
| DI5 | 02 | 0x0005 | 5 | čítanie bitu |
| DI6 | 02 | 0x0006 | 6 | čítanie bitu |
| DI7 | 02 | 0x0007 | 7 | čítanie bitu |
| DI8 | 02 | 0x0008 | 8 | čítanie bitu |
| DI9 | 02 | 0x0009 | 9 | čítanie bitu |
| DI10 | 02 | 0x000A | 10 | čítanie bitu |
| DI11 | 02 | 0x000B | 11 | čítanie bitu |
| DI12 | 02 | 0x000C | 12 | čítanie bitu |
| DI13 | 02 | 0x000D | 13 | čítanie bitu |
| DI14 | 02 | 0x000E | 14 | čítanie bitu |
| DI15 | 02 | 0x000F | 15 | čítanie bitu |

- FC02: čítanie jedného alebo viacerých discrete inputs.
- FC03, holding register `0x0022` (34): stav DI0–DI15, bit 0 = DI0, bit 15 = DI15. Zdroj používa výraz „read switch status (byte)“, ale pri 16 kanáloch treba spracovať 16-bitové slovo.

## Reléové výstupy
| Premenná | FC čítanie | FC zápis | Adresa HEX | DEC |
|---|---|---|---|---|
| DO0 | 01 | 05 / 0F | 0x0000 | 0 |
| DO1 | 01 | 05 / 0F | 0x0001 | 1 |
| DO2 | 01 | 05 / 0F | 0x0002 | 2 |
| DO3 | 01 | 05 / 0F | 0x0003 | 3 |
| DO4 | 01 | 05 / 0F | 0x0004 | 4 |
| DO5 | 01 | 05 / 0F | 0x0005 | 5 |
| DO6 | 01 | 05 / 0F | 0x0006 | 6 |
| DO7 | 01 | 05 / 0F | 0x0007 | 7 |
| DO8 | 01 | 05 / 0F | 0x0008 | 8 |
| DO9 | 01 | 05 / 0F | 0x0009 | 9 |
| DO10 | 01 | 05 / 0F | 0x000A | 10 |
| DO11 | 01 | 05 / 0F | 0x000B | 11 |

- `1` = relé zopnuté/energizované, `0` = vypnuté (s. 8).
- FC01: read coils; FC05: write single coil; FC0F (15): write multiple coils.
- FC03 / FC06 / FC10 (16), holding register `0x0020` (32): bitové pole DO0–DO11; bit 0 = DO0. Pri zápise celej masky sa môžu zmeniť všetky výstupy: **uprednostni FC05 pre jednotlivý kanál**.

## Nastavenia
| Parameter | FC | HEX | DEC | Hodnota |
|---|---|---|---|---|
| DO communication timeout | 03 / 06 | `0x0528` | 1320 | násobky 0,1 s; `0` = vypnuté |
| Save settings | 03 / 06 | `0x051F` | 1311 | zapísať `0x5A51` (23121) |

Timeout: pri absencii komunikácie počas nastavenej doby sa výstupy vrátia do **predvoleného stavu**, ktorého hodnoty ani konfiguráciu manuál nešpecifikuje (s. 8). Nezamieňať za garantované všetky OFF.

## Príklady z výrobcu (s. 8)
- FC02, 8 DI od adresy 0: `00 01 00 00 00 06 01 02 00 00 00 08`.
- FC0F, 8 DO od adresy 0, maska `0xC3`: `00 01 00 00 00 08 01 0F 00 00 00 08 01 C3`.
- Unit ID `01` je použité v príklade, **nie je potvrdené ako povinná univerzálna hodnota** pre každú inštaláciu.
