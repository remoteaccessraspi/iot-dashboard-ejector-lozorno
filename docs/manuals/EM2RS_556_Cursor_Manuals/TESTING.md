# Postup testovania

Zdroj: Leadshine EM2RS Series Modbus RS485 Stepper Drive User Manual V1.5 (2021-08-30), https://www.leadshine.com/upfiles/downloads/04bbeba0c8c1196dc41e7d54c811d7d9_1650879175499.pdf

1. Overiť typový štítok EM2RS-556, napájanie, motorové vinutia, prúdové limity a DIP prepínače.
2. Odpojiť motor od mechanizmu ventilu alebo zaistiť bezpečné testovacie podmienky.
3. Len čítanie FC03 `0x1003` (motion state) a `0x2203` (alarm); overiť adresu/baud/paritu.
4. Overiť význam stavových bitov pri enable/disable a počas testu bez záťaže.
5. Až po schválení fyzického pohybu otestovať minimálny JOG/PR pohyb s možnosťou nezávislého zastavenia.
6. Kalibrovať prepočet medzi P/R drivera a skutočným pohybom ventilu.
7. Overiť výpadok Modbus, reštart Pi, reštart drivera, fault a stratu referencie.
8. Až po úspešnom teste integrovať zápisy; v bežnom 5 s cykle uprednostniť read-only diagnostiku.

Pri akomkoľvek nesúlade zastaviť test, zaznamenať raw registre a fyzický stav.
