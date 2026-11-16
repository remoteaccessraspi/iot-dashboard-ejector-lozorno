# Testovanie bez ovládania motora

1. Skontrolovať skutočnú adresu meniča, baudrate a 8N1 v existujúcej konfigurácii.
2. Overiť, že linku RS485 v danom čase používa len jeden Modbus master.
3. Najprv vykonať iba **FC03**: `0x2100` (stav) a `0x5000` (porucha). Bežiaci program okrem nich číta blok `0x3000`–`0x3009`, vstup `0x300A` a AI2 `0x300D`.
4. Logovať surové hodnoty, čas, slave ID a prípadné výnimky.
5. Porovnať stav s displejom meniča a prevádzkovými údajmi.
6. Overiť opakované čítanie v 5-sekundovom ticku, bez kolízií s ostatnými slave zariadeniami.
7. Až po schválení skúšať zápisy na odpojenom/bezpečne pripravenom technologickom zariadení.

**Žiadne automatické FC06, RUN, STOP ani reset poruchy počas read-only testu.** STOP cez komunikáciu nie je náhradou bezpečnostného vypnutia.
