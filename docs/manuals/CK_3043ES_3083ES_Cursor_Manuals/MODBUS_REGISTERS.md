# Modbus register map — CK-3043ES / CK-3083ES

**Source:** manufacturer Vr1.0, p.9 (table), p.10 (RTU request/response).

- Function code: **03** (read holding registers).
- Addresses in the table are **zero-based protocol offsets**, not 4xxxx display labels.
- Each temperature occupies **one 16-bit register** interpreted as **signed two's complement**.
- Temperature °C = `signed_int16 / 10`.

| Logical channel (zero-based) | Manual channel (one-based) | Protocol offset (hex) | Decimal |
|---|---|---|---:|
| 0 | 1 | 0x0002 | 2 |
| 1 | 2 | 0x0003 | 3 |
| 2 | 3 | 0x0004 | 4 |
| 3 | 4 | 0x0005 | 5 |
| 4 | 5 | 0x0006 | 6 |
| 5 | 6 | 0x0007 | 7 |
| 6 | 7 | 0x0008 | 8 |
| 7 | 8 | 0x0009 | 9 |

CK-3043ES: read **4 registers** starting at address 2. CK-3083ES: read **8 registers** starting at address 2.

Examples: 314 -> 31.4 °C; raw signed -389 -> -38.9 °C. If library returns unsigned 16-bit values, convert with `raw - 65536 if raw >= 32768 else raw`.

## Verified RTU request (manufacturer p.10)
`01 03 00 02 00 04 E5 C9` = slave 1, FC03, start 2, count 4, CRC. Example response: `01 03 08 06 18 03 D9 01 5A 03 15 70 CC`, corresponding to 156.0, 98.5, 34.6, 78.9 °C.

## Documentation discrepancy — do not implement blindly
Page 9 also includes rows labelled digital outputs (FC01/05/0F, addresses 0–7 and 20). The device is described as an RTD input collector, and no digital output terminals are shown in the wiring diagram. Treat these rows as **unverified/copy-paste material**, not supported writable outputs. Do not issue FC05/FC0F to this hardware without explicit manufacturer confirmation.

The manual does not specify diagnostic values for broken sensors, or configuration holding registers for RTD type. Do not invent them.
