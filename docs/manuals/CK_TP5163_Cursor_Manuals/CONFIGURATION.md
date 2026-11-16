# CK-TP5163 — sieť a prevádzkové nastavenia

## Sieť
- Továrenská IP: `192.168.1.30` (s. 7).
- Modbus TCP port: `502` (s. 7).
- 2× RJ45, 10/100 Mbps, Ethernet cascading, AUTO-MDIX (s. 6, 9).
- IP adresa, maska a brána sa **nedajú bezpečne konfigurovať podľa dodaného manuálu**: nie sú uvedené postup ani registre. Vyžiadaj návod výrobcu alebo overený konfiguračný nástroj.

## Timeout relé
- Holding register `0x0528` = 1320, FC03 read / FC06 write.
- Jednotka `0.1 s`. Príklad: `50` znamená `5.0 s`.
- `0` = funkcia deaktivovaná.
- Po uplynutí intervalu bez komunikácie sa výstupy vrátia do **predvoleného stavu** (výrobca nešpecifikuje konkrétnu hodnotu).
- Pozor: manuál hovorí „no communication“; nepreukazuje, že samotné čítanie z iného klienta alebo iná Modbus prevádzka nebude timeout obnovovať. Otestovať v reálnej topológii.

## Uloženie nastavení
- Zápis FC06, holding register `0x051F` = 1311, hodnota `0x5A51`.
- Najprv prečítaj aktuálny timeout; zmena až po potvrdení operátorom.
- Po zápise over čítaním a po reštarte over persistenciu.
- Automaticky nespúšťaj zápis pri každom štarte programu.

## Integrácia Raspberry Pi
- Odporúčaný projektový polling: 5 s (nie parameter výrobcu).
- Čítanie DI: FC02 offset 0, count 16.
- Čítanie DO: FC01 offset 0, count 12.
- Jednotlivý DO: FC05 offset `i`.
- Reconnect s backoff, timeout požiadavky, audit zmien a oddelenie read/write oprávnení.
