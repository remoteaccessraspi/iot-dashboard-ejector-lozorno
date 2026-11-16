# RS485 konfigurácia
Zdroj: Vr1.0, str. 7–9.

- Protokol: Modbus RTU, slave/server.
- Predvolené: **9600 baud, 8 dátových bitov, bez parity, 1 stop bit (8N1)**; adresa **1**.
- Povolené adresy protokolu: 1–247.
- Výrobcom uvedené rýchlosti: 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200 baud.
- Dvojmiestny mechanický volič adresy: **00** používa softvérovo uloženú adresu; **01–99** používa polohu voliča. Poloha sa načíta pri zapnutí/reštarte, nie okamžite.
- PDF spomína zmenu adresy a rýchlosti príkazmi, ale **neobsahuje mapu ich zápisových registrov**. Bez dodatočného podkladu nezapisovať.

## Návrh konfigurácie Raspberry Pi (príklad, nie továrenské hodnoty)
```yaml
ck8082r:
  enabled: true
  port: /dev/serial/by-id/REPLACE_WITH_ACTUAL_ADAPTER
  baudrate: 9600
  bytesize: 8
  parity: N
  stopbits: 1
  slave_id: 1
  start_register: 96
  count: 8
  poll_interval_seconds: 5
  timeout_seconds: 1
```

Na spoločnej RS485 zbernici zabezpečiť jediný plánovač komunikácie, aby sa požiadavky neprekrývali. Overiť port podľa skutočného USB/RS485 adaptéra. Nenastavovať automaticky všetkým modulom adresu 1.
