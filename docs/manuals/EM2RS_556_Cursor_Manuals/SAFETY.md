# Zapojenie a bezpečnosť

Zdroj: Leadshine EM2RS Series Modbus RS485 Stepper Drive User Manual V1.5 (2021-08-30), https://www.leadshine.com/upfiles/downloads/04bbeba0c8c1196dc41e7d54c811d7d9_1650879175499.pdf

- CN1 20–50 VDC, CN2 motorové vinutia A+/A− B+/B−; skutočné piny overiť podľa PDF str. 15–17.
- CN3: DI1–DI7 (12–24 V), DO1–DO3 (max 24 V / 100 mA), CN4 RS485, CN5 RS232.
- Pred zapájaním odpojiť napájanie; rešpektovať výstrahy výrobcu o zostatkovom napätí a čase čakania.
- Nikdy neodpájať motor pod napätím; núdzové zastavenie musí byť riešené nezávisle od Raspberry Pi a Modbus.
- Bez koncových spínačov a enkódera je poloha len odhad. Mechanický doraz nesmie slúžiť ako neobmedzená ochrana proti prebehu.
- Pri strate komunikácie nepredpokladať automatické zastavenie, kým nie je funkcia potvrdená konfiguráciou a skúškou.
- Po chybe nepokračovať automaticky v pohybe, kým nie je príčina odstránená.
