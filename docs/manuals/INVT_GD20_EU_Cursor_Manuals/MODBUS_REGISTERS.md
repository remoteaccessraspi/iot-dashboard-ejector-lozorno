# Modbus register map — GD20-EU

Zdroj: INVT Goodrive20-EU User Manual V1.9, `docs/GD20-EU VFD Manual _V1.9.pdf`, kapitola 7.4. Čísla strán sú strany PDF súboru, nie tlačené čísla v päte.

Adresa je **hexadecimálna adresa protokolu**, nie číslo 4xxxx. Čítanie je FC03, zápis jedného registra FC06.

Pravidlo adresy parametra (kap. 7.4.1, str. 135): horný bajt je číslo skupiny v hex, dolný bajt je index v hex. `P05.05` → `0x0505`, `P10.01` → `0x0A01`, `P14.00` → `0x0E00`. Zápis len do RAM, bez EEPROM, má horný bit skupiny 1: `P00.07` → `0x8007`. Táto RAM adresa sa dá len zapisovať. Program ju nepoužíva.

Stĺpec **Program** hovorí, čo s registrom robí `iot_core/devices/invt_gd20.py`. Kľúč je názov v `config/devices/invt_gd20.yaml`.

## Riadiace a stavové registre (kap. 7.4.2, str. 136–139)

| Adresa | Význam | Kódovanie | Kľúč v YAML | Program |
|---|---|---|---|---|
| `0x2000` | riadiaci príkaz, R/W | `1` vpred, `2` vzad, `3` jog vpred, `4` jog vzad, `5` stop, `6` voľný dobeh, `7` reset poruchy, `8` stop jogu | `control` | zápis `1` pri RUN a `5` pri STOP |
| `0x2001` | žiadaná frekvencia, R/W | 0–Fmax, krok 0,01 Hz | — | nepoužíva; frekvenciu určuje PID |
| `0x2002` | PID referencia, R/W | 0–1000 = 0–100,0 % | `pid_reference` | zápis zo `gd20_setpoint_kpa`, 0–1500 kPa → 0–1000 |
| `0x2003` | PID spätná väzba cez komunikáciu, R/W | 0–1000 = 0–100,0 % | `pid_feedback_command` | nepoužíva; spätná väzba ide z AI2 |
| `0x2100` | stavové slovo 1, R | viď tabuľku nižšie | `status_word` | čítanie v každom cykle; chod je hodnota 1 alebo 2 |
| `0x3000` | prevádzková frekvencia, R | 0,01 Hz | `running_frequency` | čítanie v bloku `0x3000`–`0x3009`, DB `frequency_actual_hz` |
| `0x3001` | nastavená frekvencia, R | 0,01 Hz | `set_frequency` | čítanie v tom istom bloku, DB `frequency_set_hz` |
| `0x3002` | napätie medziobvodu, R | 0,1 V | `dc_bus_voltage` | čítanie v bloku, DB `dc_bus_voltage_v` |
| `0x3003` | výstupné napätie, R | 1 V | `output_voltage` | čítanie v bloku, DB `output_voltage_v` |
| `0x3004` | výstupný prúd, R | 0,1 A | `output_current` | čítanie v bloku, DB `output_current_a` |
| `0x3005` | otáčky, R | 1 rpm | `motor_speed` | čítanie v bloku, DB `motor_speed_rpm`; alias v YAML je `NA` |
| `0x3006` | výstupný výkon, R | −300,0–300,0 %, krok 0,1, signed | `output_power` | čítanie v bloku, do DB sa neukladá |
| `0x3007` | výstupný moment, R | −250,0–250,0 %, krok 0,1, signed | `output_torque` | čítanie v bloku, do DB sa neukladá |
| `0x3008` | PID referencia, R | −100,0–100,0 %, krok 0,1, signed | `pid_setting` | čítanie v bloku, DB `pid_setpoint_kpa` |
| `0x3009` | PID spätná väzba, R | −100,0–100,0 %, krok 0,1, signed | `pid_feedback` | čítanie v bloku, DB `pid_feedback_kpa` |
| `0x300A` | stav vstupov, R | 000–1FF | `digital_input_state` | čítanie; bit3 je externý stop na S4 |
| `0x300C` | AI1, R | 0,00–10,00 V, krok 0,01 V | `ai1` | nepoužíva |
| `0x300D` | AI2, R | 0,00–10,00 V, krok 0,01 V | `ai2` | čítanie; prepočet na kPa, DB `ai2_kpa` |
| `0x5000` | kód poruchy, R | podľa tabuľky porúch | `fault_code` | čítanie, DB `fault_code` |

`0x2001` a `0x3001` sú dva rôzne registre. Prvý je zápis žiadanej frekvencie, druhý je čítanie frekvencie, ktorú menič práve používa. Program zapisuje PID referenciu `0x2002` a číta `0x3001`.

`0x2002` je relatívna hodnota 0–100,0 %. Nie je to register v kPa. Prevod kPa → 0–1000 je v programe podľa `engineering_min` a `engineering_max` v YAML (0–1500 kPa).

PDF v tej istej kapitole uvádza aj `0x2004`–`0x200E`, `0x2101`–`0x2103`, `0x300B` a `0x300E`–`0x3016`. Program ich nepoužíva. `0x300B` je v PDF označený rovnako ako `0x300A`, „Input state“.

### Stavové slovo `0x2100`

| Hodnota | PDF, str. 137 | YAML |
|---|---|---|
| `1` | Forward running | RUN FWD |
| `2` | Forward running | RUN REV |
| `3` | Stop | STOP |
| `4` | Fault | FAULT |
| `5` | POFF state | POFF |
| `6` | Pre-exciting state | PRE-EXCITING |

Hodnota 2 je v stavovej tabuľke napísaná druhýkrát ako „Forward running“. V riadiacom príkaze `0x2000` je `0002H` v tom istom PDF „Reverse running“. Program berie 1 aj 2 ako chod, takže na RUN a STOP označenie hodnoty 2 vplyv nemá.

## Parametre, ktoré má YAML (skupiny P00, P01, P05, P09, P14)

Adresy sú podľa pravidla z kapitoly 7.4.1. Pri štarte mastera sa zapisujú len štyri parametre zo `setup.parameters`, a len keď sa od meniča líšia. P00.01 a P05.04 sa zapíšu, až keď menič stojí.

| Parameter | Adresa | PDF | YAML `required_value` | Program |
|---|---|---|---|---|
| P00.01 | `0x0001` | `2` = príkaz z komunikácie (str. 37) | 2 | zápis pri štarte, len keď menič stojí |
| P00.03 | `0x0003` | max. frekvencia, 0,01 Hz (str. 40) | — | nezapisuje |
| P00.04 | `0x0004` | horný limit frekvencie, 0,01 Hz | — | nezapisuje |
| P00.05 | `0x0005` | dolný limit frekvencie, 0,01 Hz | — | nezapisuje |
| P00.06 | `0x0006` | zdroj frekvencie A; `7` = procesný PID (str. 40) | 7 | nečíta ani nezapisuje; sedmička v YAML je len očakávaná hodnota |
| P00.11 | `0x000B` | rozbeh, 0,0–3600,0 s | — | nezapisuje |
| P00.12 | `0x000C` | dobeh, 0,0–3600,0 s | — | nezapisuje |
| P01.21 | `0x0115` | reštart po výpadku; `0` vypnutý, `1` zapnutý (str. 50) | 0 | zápis pri štarte |
| P05.04 | `0x0504` | funkcia S4; `6` = voľný dobeh (str. 62) | 6 | zápis pri štarte, len keď menič stojí |
| P05.10 | `0x050A` | polarita vstupov; bit3 = S4, `1` = obrátená logika (str. 64) | 8 | zápis pri štarte |
| P09.00 | `0x0900` | zdroj PID referencie; `6` = Modbus (str. 88) | 6 | nezapisuje |
| P09.02 | `0x0902` | zdroj PID spätnej väzby; `1` = AI2 (str. 89) | 1 | nezapisuje |
| P09.03 | `0x0903` | smer PID; `0` kladný, `1` záporný | — | nezapisuje |
| P09.04 | `0x0904` | Kp, 0,00–100,00, default 1,00 | — | nezapisuje |
| P09.05 | `0x0905` | Ti, 0,00–10,00 s, default 0,10 | — | nezapisuje |
| P09.06 | `0x0906` | Td, 0,00–10,00 s, default 0,00 | — | nezapisuje |
| P14.00 | `0x0E00` | slave adresa, 1–247, default 1 (str. 100) | — | nezapisuje |
| P14.01 | `0x0E01` | baud; `3` = 9600, `4` = 19200 a je default (str. 101) | 3 | nezapisuje |
| P14.02 | `0x0E02` | rámec; `0` = 8N1 RTU, default je `1` = 8E1 (str. 101) | 0 | nezapisuje |
| P14.04 | `0x0E04` | timeout komunikácie, 0,0–60,0 s | — | nezapisuje |

P00.07 je zdroj frekvencie B, nie druhý zápis P00.06. PID beží, keď je `7` v P00.06 alebo v P00.07 (str. 40 a 88). Master ani jeden z nich nečíta a nezapisuje. V YAML je očakávaná hodnota len pri P00.06.

AI2 pri voľbe prúdu 0–20 mA hlási menič ako 0–10 V (poznámka pri P00.07, str. 40). Register `0x300D` je preto vo voltoch. Prepočet 4–20 mA na 0–1500 kPa je v YAML, nie v registri meniča.
