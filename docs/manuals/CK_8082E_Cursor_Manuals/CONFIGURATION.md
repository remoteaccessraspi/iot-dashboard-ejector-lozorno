# Konfigurácia pripojenia

## Ethernet / Modbus TCP
Výrobca potvrdzuje Modbus TCP a dva Ethernet porty pre kaskádovanie (str. 5–8). **Neuvádza predvolenú IP, masku, TCP port ani postup zmeny IP.** Port 502 je štandard Modbus TCP, nie explicitný údaj tohto PDF. Konkrétnu IP a Unit ID zistiť z reálneho zariadenia alebo od výrobcu.

## RS485 / Modbus RTU
Výrobcom uvedené predvolené nastavenia (str. 8): **9600 baud, 8N1, adresa 01**. Podporované rýchlosti: 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200. Adresy 1–247.

Pripojenie: A = RS485+, B = RS485− podľa tabuľky svoriek (str. 6). Zabezpečiť správnu topológiu, ukončenie a jedného RTU mastera na zbernici.

## Adresové prepínače
Na fotografii sú mechanické prepínače ×1 a ×10; text v tomto PDF nepopisuje presný postup nastavenia pre CK-8082E. Bez overenia nepovažovať ich účinok na TCP adresáciu za zdokumentovaný.

## Prevádzka
Pre existujúci projekt použiť 5 s polling, s timeoutom, obmedzenými retry, bez blokovania ďalších zariadení. Zmenu parametrov zariadenia vykonať iba po explicitnom schválení; konfiguračné registre na zápis nie sú uvedené.
