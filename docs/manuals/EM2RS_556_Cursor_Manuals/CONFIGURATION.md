# Komunikácia a nastavenie

Zdroj: Leadshine EM2RS Series Modbus RS485 Stepper Drive User Manual V1.5 (2021-08-30), https://www.leadshine.com/upfiles/downloads/04bbeba0c8c1196dc41e7d54c811d7d9_1650879175499.pdf

- Modbus RTU RS485, CN4; CN5 RS232 len na tuning; CN1 napájanie; CN2 motor.
- Slave ID cez DIP SW1–SW5, baud cez SW6–SW7, terminácia SW8 (PDF str. 15–18).
- Pred integráciou odčítať fyzické DIP prepínače a overiť baud, paritu, adresu; **nepredpokladať** 9600 8N1 ani ID 1 iba z projektu.
- Raspberry Pi používa zdieľanú RS485 zbernicu: serializovať všetky Modbus transakcie; čítanie stavov v existujúcom 5 s ticku.
- EEPROM uloženie `0x1801=0x2211` len po autorizovanej zmene perzistentnej konfigurácie; časté zápisy do EEPROM zakázané.
- Pr0.00 `0x0001` default 10000 P/R. Projektové „200 pulzov na otáčku“ je mechanický predpoklad, nie automaticky nastavenie drivera.
