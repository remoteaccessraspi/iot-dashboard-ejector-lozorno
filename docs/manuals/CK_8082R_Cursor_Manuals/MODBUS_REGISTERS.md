# Modbus RTU — mapa registrov
Zdroj: výrobca Vr1.0, str. 8–9.

- Funkcia **FC03** (`Read Holding Registers`)
- Začiatočná adresa v protokole: `0x0060` = 96 (zero-based)
- 8 po sebe idúcich registrov; jedno 16-bit signed číslo na kanál
- Fyzikálna hodnota = `signed_int16 / 1000` (mA alebo V podľa osadeného rozsahu)

| Kanál | Hex | Decimal zero-based | PLC 4xxxx podľa PDF |
|---|---|---:|---:|
| AI0 | 0x0060 | 96 | 40097 |
| AI1 | 0x0061 | 97 | 40098 |
| AI2 | 0x0062 | 98 | 40099 |
| AI3 | 0x0063 | 99 | 40100 |
| AI4 | 0x0064 | 100 | 40101 |
| AI5 | 0x0065 | 101 | 40102 |
| AI6 | 0x0066 | 102 | 40103 |
| AI7 | 0x0067 | 103 | 40104 |

Príklad RTU request zo str. 9 pre 4 kanály: `01 03 00 60 00 04 44 17` (posledné 2 bajty CRC). Pri knižnici Modbus CRC zostavuje knižnica.

**Dôležité:** 24-bit je rozlíšenie interného ADC, nie formát dát na týchto registroch. Nepoužiť 32-bit float ani dva registre na kanál. Zápisové registre a príkazy na zmenu komunikačných parametrov nie sú v PDF uvedené — nevymýšľať.
