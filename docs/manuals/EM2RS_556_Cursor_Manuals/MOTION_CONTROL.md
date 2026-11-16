# Riadenie pohybu a homing

Zdroj: Leadshine EM2RS Series Modbus RS485 Stepper Drive User Manual V1.5 (2021-08-30), https://www.leadshine.com/upfiles/downloads/04bbeba0c8c1196dc41e7d54c811d7d9_1650879175499.pdf

## Výrobcom dokumentované funkcie
- `0x6002` (Pr8.02) zápis `0x10` až `0x1F`: spustiť PR path 0–15; `0x20` homing; `0x21` manuálne nastaviť nulovú polohu; `0x40` quick stop (str. 48 a 60 PDF). Čítanie `0x000P` = path P hotová, `0x010P` = path P beží, `0x0200` = čaká na polohovanie, `0x020P` = chyba sledovania v path P.
- `0x1801=0x4001` CW JOG, `0x4002` CCW JOG, podľa manuálu minimálne 50 ms medzi požadovanými JOG zápismi; nejde o bežný single-step príkaz.
- PR path 0: `0x6200` mód (bity 0–3 = 1 poloha, bit6 0 absolútna / 1 relatívna), `0x6201/0x6202` cieľ high/low, `0x6203` rýchlosť v rpm, `0x6204/0x6205` acc/dec v ms/1000 rpm, `0x6206` pauza (kap. 5.5, str. 42 a 61 PDF).
- Poloha drivera: `0x602C/0x602D` (Pr8.44/Pr8.45) actual position high/low, nuluje sa po úspešnom homingu (str. 61 PDF).

## Ako pohyb robí program
- Bežný pohyb: zápis `0x6200=0x01` (absolútna), cieľ do `0x6201/0x6202`, potom `0x6002=0x10`.
- Homing: zápis `0x6200=0x41` (relatívna), `valve.homing_steps` impulzov v smere `valve.homing_direction` do `0x6201/0x6202` (pri CLOSE so záporným znamienkom), `0x6002=0x10`. Po dojazde porovná prírastok `0x602C/0x602D` s touto hodnotou, zapíše `0x6002=0x21` a čaká, kým poloha drivera ukáže 0.
- Homing drivera `0x6002=0x20` a registre `0x600A`–`0x6015` program nepoužíva.
- Quick stop: `0x6002=0x40`.
- Enable: `0x000F` (Pr0.07) 1 pred pohybom a 0 po ňom; `0x0145` (Pr4.02) sa pri štarte nastaví na 0, aby DI1 enable neriadil.

## ETS 12C — projektová stratégia
- Nominálny rozsah 0–600 mechanických impulzov; rýchlosť 50 rpm; referencovanie 650 impulzov do dorazu je iba existujúci projektový postup, **nie výrobcom dokumentovaný bezpečný homing**.
- Bez koncových spínačov a enkódera nemožno automaticky potvrdiť mechanický doraz; vyhodnotiť riziko preťaženia a poškodenia ventilu.
- Po reštarte alebo chybe polohy nastav `em2rs_position_valid=false`; automatický návrat na doraz bez explicitného schválenia zakázaný.
- Pred spustením: schválený smer, prúd, P/R, rýchlosť, rozsah, bezpečné zastavenie a watchdog systému.
