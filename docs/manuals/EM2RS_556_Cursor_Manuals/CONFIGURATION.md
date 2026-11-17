# Komunikácia a nastavenie

Zdroj: Leadshine EM2RS Series Modbus RS485 Stepper Drive User Manual V1.5 (2021-08-30), https://www.leadshine.com/upfiles/downloads/04bbeba0c8c1196dc41e7d54c811d7d9_1650879175499.pdf

- Modbus RTU RS485, CN4; CN5 RS232 len na tuning; CN1 napájanie; CN2 motor.
- Slave ID cez DIP SW1–SW5, baud cez SW6–SW7, terminácia SW8 (PDF str. 15–18).
- Pred integráciou odčítať fyzické DIP prepínače a overiť baud, paritu, adresu; **nepredpokladať** 9600 8N1 ani ID 1 iba z projektu.
- Raspberry Pi používa zdieľanú RS485 zbernicu: serializovať všetky Modbus transakcie; čítanie stavov v existujúcom 5 s ticku.
- EEPROM uloženie `0x1801=0x2211` len po autorizovanej zmene perzistentnej konfigurácie; časté zápisy do EEPROM zakázané.
## Nastavenie tohto stroja

Budič krokového motora EM2RS-556, step motor driver, je nastavený takto.

Továrenský default Pr0.00 v PDF je 10000 pulzov na otáčku. Na tomto budiči platí tabuľka nižšie. Master ju pri štarte raz porovná a zapíše len hodnotu, ktorá sa od budiča líši. Potom registre len číta. Do EEPROM nastavenie neukladá.

| Parameter | Hodnota | Význam |
|---|---|---|
| Pr0.00 | 200 | pulzy na otáčku |
| Pr5.00 | 0,8 A | špičkový prúd, v registri slovo 8 |
| Path0 mode | 1 | absolútna poloha |
| Path0 speed | 50 | otáčky za minútu |
| Path0 acceleration | 100 | zrýchlenie |
| Path0 deceleration | 100 | spomalenie |
| Path0 pause | 0 | pauza po pohybe |
