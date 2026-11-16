# CK-5009E — Modbus registre

Zdroj: Vr1.0, str. 8–9. Adresy v tabuľke sú **nulovo indexované Modbus PDU adresy**, nie PLC notácia.

| Kanál | Coil address (hex) | Decimal | Funkcie |
|---|---|---:|---|
| DO0 | 0x0000 | 0 | FC01 read, FC05 write, FC0F write |
| DO1 | 0x0001 | 1 | FC01/05/0F |
| DO2 | 0x0002 | 2 | FC01/05/0F |
| DO3 | 0x0003 | 3 | FC01/05/0F |
| DO4 | 0x0004 | 4 | FC01/05/0F |
| DO5 | 0x0005 | 5 | FC01/05/0F |
| DO6 | 0x0006 | 6 | FC01/05/0F |
| DO7 | 0x0007 | 7 | FC01/05/0F |

- `FC01`: čítanie stavu výstupných cievok.
- `FC05`: zápis jednej cievky; v Modbus protokole ON = `0xFF00`, OFF = `0x0000`.
- `FC0F` (15): zápis viacerých cievok. Pri zápise 8 výstupov je bit 0 = DO0, bit 7 = DO7.
- Príklad výrobcu (str. 9): `01 0F 00 00 00 08 01 C3 BE C4` nastaví DO0, DO1, DO6, DO7 na 1; ostatné na 0. Príklad je rámec RTU vrátane CRC, **nie** TCP payload.
- Výrobca uvádza aj `FC03`/`FC06` a register `0x0020` pre bitovú masku DO0–DO15 (str. 8). Pre CK-5009E je to rodinná tabuľka a zápis do tohto registra **nepoužívať bez overenia**.
- Str. 8 uvádza `FC02` a register `0x0022` pre DI; CK-5009E je však 8DO-only. **Nepoužívať DI adresy pre tento model.**
- `FC10` (hex 0x10 = 16) je spomenuté v texte str. 8, ale nie je konzistentne uvedené v zozname podporovaných funkcií. Nepoužívať bez testu.

## Adresná disciplína
Python knižnica zvyčajne očakáva PDU adresy 0–7. PLC číslo 0001 z manuálu neznamená PDU adresu 1 pre DO0. Nikdy nepridávaj +1 automaticky.
