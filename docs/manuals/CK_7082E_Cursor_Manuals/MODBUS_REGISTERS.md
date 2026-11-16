# CK-7082E — mapa Modbus registrov

Zdroj: manuál Vr1.1, str. 8–9.

## Read holding registers (FC03)

| Kanál | Hex adresa (zero-based) | Decimal offset | PLC 4xxxx podľa manuálu | Formát |
|---|---|---:|---:|---|
| AI0 | `0x0060` | 96 | 40097 | signed int16 / 1000 |
| AI1 | `0x0061` | 97 | 40098 | signed int16 / 1000 |
| AI2 | `0x0062` | 98 | 40099 | signed int16 / 1000 |
| AI3 | `0x0063` | 99 | 40100 | signed int16 / 1000 |
| AI4 | `0x0064` | 100 | 40101 | signed int16 / 1000 |
| AI5 | `0x0065` | 101 | 40102 | signed int16 / 1000 |
| AI6 | `0x0066` | 102 | 40103 | signed int16 / 1000 |
| AI7 | `0x0067` | 103 | 40104 | signed int16 / 1000 |


- Čítanie všetkých kanálov: FC03, štart `0x0060` (96), počet 8.
- Registre sú 16-bit signed, big-endian Modbus register; napr. `0xF6D7` = -2345 -> -2.345 V pre napäťový variant (str. 8–9).
- `16781` -> `16.781 mA` pri prúdovom variante.
- PLC adresa 40097 je iba referenčný zápis; v knižnici používaj offset 96, **nie 40097**.
- Manuál explicitne uvádza len FC03 na čítanie; zápisové registre a konfiguráciu rozsahu neuvádza. Neskúšaj FC06/FC16 na nezdokumentovaných adresách.
- Ukážky RTU/TCP na str. 8–9 používajú 4 kanály len na ilustráciu; fyzický CK-7082E má 8 kanálov.
