# Overené Modbus registre

Zdroj: Leadshine EM2RS Series Modbus RS485 Stepper Drive User Manual V1.5 (2021-08-30), `docs/EM2RS_User_Manual_V1.5.pdf`. Čísla strán sú strany PDF súboru, nie tlačené čísla v päte.

Adresa je **zero-based PDU register** v hexadecimálnom zápise, nie číslo 4xxxx. Parametre môžu zaberať dvojicu 16-bitových registrov (high/low), preto ich nikdy nečítať ako automaticky samostatné 16-bitové hodnoty bez kontroly (kap. 4.3.1).

Stĺpec **Program** hovorí, čo s registrom robí `iot_core/devices/em2rs_556.py`. Kľúč je názov v `config/devices/em2rs_556.yaml`.

## Parametre drivera (kap. 4.3.1, str. 25–26, Appendix str. 58–59)

| Register | Pr | Funkcia | Operácia | Kľúč v YAML | Program |
|---|---|---|---|---|---|
| `0x0001` | Pr0.00 | Pulse/revolution, default 10000, rozsah 200–51200 | R/W | `pulse_per_revolution` | čítanie v každom cykle; pri štarte mastera zápis 200, ak sa líši |
| `0x0007` | Pr0.03 | smer motora, 0 CW, 1 CCW | R/W | — | nepoužíva |
| `0x000F` | Pr0.07 | software forced enable, 1 = enable bez ohľadu na IO | R/W | `forced_enable` | zápis 1 pred pohybom, 0 po pohybe |
| `0x0145` | Pr4.02 | SI1 (DI1), default 0x88 = enable, N.C. | R/W | `si1` | pri štarte zápis 0, enable potom riadi len Pr0.07 |
| `0x0191` | Pr5.00 | peak current, jednotka 0,1 A | R/W | `peak_current` | čítanie v každom cykle; pri štarte zápis 8 (0,8 A), ak sa líši |
| `0x01E1` | Pr6.00 | JOG velocity, 0–5000 rpm, default 60 | R/W | — | nepoužíva |
| `0x0201` | Pr6.16 | firmware information, len surové slovo | R | `firmware` | nepoužíva |

## Stav a diagnostika (kap. 4.3.4 a 4.4.2, str. 29–31, Appendix str. 59–60)

| Register | Funkcia | Operácia | Kľúč v YAML | Program |
|---|---|---|---|---|
| `0x1003` | motion state: bit0 fault, bit1 enabled, bit2 running, bit4 command complete, bit5 path complete, bit6 homing complete | R | `motion_status` | čítanie v každom cykle, používa len bit2 (running) |
| `0x1012/0x1013` | profile position, high/low | R | — | nepoužíva |
| `0x1014/0x1015` | feedback position, high/low | R | — | nepoužíva |
| `0x1044/0x1045` | profile velocity, high/low, rpm | R | — | nepoužíva |
| `0x1046/0x1047` | feedback velocity, high/low, rpm | R | — | nepoužíva |
| `0x1801` | auxiliary control word: 0x1111 reset alarm, 0x2211 EEPROM save, 0x4001 CW JOG, 0x4002 CCW JOG | W | — | nepoužíva; adresa je v `_SETUP_FORBIDDEN` |
| `0x1901` | EEPROM save status: 0x5555 úspech, 0xAAAA zlyhanie; čítanie môže status vynulovať | R | — | nepoužíva |
| `0x2203` | current alarm: 0x01 overcurrent, 0x02 overvoltage, 0x40 current sampling, 0x80 shaft lock, 0x100 autotune, 0x200 EEPROM | R | `current_alarm` | nepoužíva |

## PR parametre (kap. 5.2–5.5, str. 37–48, Appendix str. 60–61)

| Register | Pr | Funkcia | Operácia | Kľúč v YAML | Program |
|---|---|---|---|---|---|
| `0x6000` | Pr8.00 | PR global control: bit0 CTRG hrana, bit1 soft limit, bit2 homing po zapnutí, bit4 typ CTRG | R/W | `pr_global_control` | nepoužíva |
| `0x6002` | Pr8.02 | PR trigger: zápis 0x1P path P, 0x20 homing, 0x21 nulová poloha, 0x40 quick stop; čítanie 0x000P hotovo, 0x010P beží, 0x0200 čaká na polohovanie, 0x020P chyba sledovania v path P | R/W | `command` | zápis 0x10, 0x21, 0x40; 0x20 nepoužíva; adresa je v `_SETUP_FORBIDDEN` |
| `0x6006/0x6007` | Pr8.06/Pr8.07 | soft limit +, high/low | R/W | `soft_limit_positive_*` | nepoužíva |
| `0x6008/0x6009` | Pr8.08/Pr8.09 | soft limit −, high/low | R/W | `soft_limit_negative_*` | nepoužíva |
| `0x600A` | Pr8.10 | homing mode: bit0 smer, bit1 pohyb po homingu, bit2 metóda | R/W | `homing_mode` | nepoužíva |
| `0x600F` | Pr8.15 | homing high velocity, rpm | R/W | `homing_high_velocity` | nepoužíva |
| `0x6010` | Pr8.16 | homing low velocity, rpm | R/W | `homing_low_velocity` | nepoužíva |
| `0x6011` | Pr8.17 | homing acc, ms/1000 rpm | R/W | `homing_acceleration` | nepoužíva |
| `0x6012` | Pr8.18 | homing dec, ms/1000 rpm | R/W | `homing_deceleration` | nepoužíva |
| `0x6015` | Pr8.19 | homing over-travel | R/W | `homing_overtravel` | nepoužíva |
| `0x6017` | Pr8.23 | quick stop time, ms | R/W | `quick_stop_time` | nepoužíva |
| `0x601D` | Pr8.29 | PR alarm: 0x100 limit switch pri homingu, 0x102 homing over-travel, 0x20P limit switch v path P | R | `pr_alarm` | nepoužíva |
| `0x602A/0x602B` | Pr8.42/Pr8.43 | profile position, high/low; nuluje sa po úspešnom homingu | R | `profile_position_*` | nepoužíva |
| `0x602C/0x602D` | Pr8.44/Pr8.45 | actual position, high/low; nuluje sa po úspešnom homingu | R | `actual_position_*` | čítanie v každom cykle ako signed 32 bit; kontrola homingu a dojazdu, DB `actual_position_steps` |
| `0x6200` | Pr9.00 | path 0 mode: bity 0–3 = 1 poloha, bit6 0 absolútna / 1 relatívna | R/W | `path0_mode` | čítanie v bloku; pri štarte zápis 1, ak sa líši; pri pohybe zápis 0x01 (absolútna) a 0x41 (relatívna) |
| `0x6201/0x6202` | Pr9.01/Pr9.02 | path 0 position, high/low | R/W | `target_position_*` | čítanie v bloku; zápis cieľa pred štartom path 0 |
| `0x6203` | Pr9.03 | path 0 velocity, rpm | R/W | `speed` | čítanie v bloku; pri štarte zápis 50, ak sa líši |
| `0x6204` | Pr9.04 | path 0 acc, ms/1000 rpm | R/W | `acceleration` | čítanie v bloku; pri štarte zápis 100, ak sa líši |
| `0x6205` | Pr9.05 | path 0 dec, ms/1000 rpm | R/W | `deceleration` | čítanie v bloku; pri štarte zápis 100, ak sa líši |
| `0x6206` | Pr9.06 | path 0 pause time | R/W | `pause_time` | čítanie v bloku; pri štarte zápis 0, ak sa líši |

Program číta `0x6200`–`0x6206` jedným FC03 blokom so 7 slovami.

## Dve sady polohy

Driver hlási polohu na dvoch miestach. Program číta druhú sadu.

| Význam | Stavové registre (str. 29) | PR parametre (str. 60–61) |
|---|---|---|
| profilová poloha | `0x1012/0x1013` | `0x602A/0x602B` |
| skutočná poloha | `0x1014/0x1015` (feedback position) | `0x602C/0x602D` (actual position) |

PDF neuvádza, či sa obe sady líšia hodnotou. EM2RS-556 nemá enkóder, takže „actual“ ani „feedback“ nie je nezávislé meranie mechanickej polohy ventilu. V PDF je pri `0x602D` preklep v názve „Actual position H“; popis hovorí o dolných 16 bitoch.

**Pozor:** 0x1801 obsahuje aj nebezpečné resetovacie povely 0x2222 a 0x2233. Cursor ich nesmie automaticky vykonávať. Tabuľka nie je kompletný register dump; ďalšie registre hľadať v kap. 4–5 a Appendix A pôvodného PDF.
