# Modbus TCP register map — CK-TP7XXX

Source: manufacturer PDF Vr1.1, page 7. **Read-only documented function:** FC03 (Read Holding Registers).

- Default IP: `192.168.1.30`; TCP port `502`.
- Manufacturer examples use Unit ID `1`; actual device Unit ID should be checked.
- Register addresses below are **zero-based protocol offsets**. PLC 4xxxx labels are display conventions; do not subtract 40001 twice.
- Each sample is **one signed 16-bit register**, big-endian Modbus word; convert two's-complement to signed and divide by `1000`.

| Channel | Hex offset | Decimal offset | PLC label |
|---|---|---|---|
| AI0 | `0x0060` | 96 | 40097 |
| AI1 | `0x0061` | 97 | 40098 |
| AI2 | `0x0062` | 98 | 40099 |
| AI3 | `0x0063` | 99 | 40100 |
| AI4 | `0x0064` | 100 | 40101 |
| AI5 | `0x0065` | 101 | 40102 |
| AI6 | `0x0066` | 102 | 40103 |
| AI7 | `0x0067` | 103 | 40104 |
| AI8 | `0x0068` | 104 | 40105 |
| AI9 | `0x0069` | 105 | 40106 |
| AI10 | `0x006A` | 106 | 40107 |
| AI11 | `0x006B` | 107 | 40108 |
| AI12 | `0x006C` | 108 | 40109 |
| AI13 | `0x006D` | 109 | 40110 |
| AI14 | `0x006E` | 110 | 40111 |
| AI15 | `0x006F` | 111 | 40112 |


## Interpretation

```python
def decode_ai(register: int) -> float:
    if not 0 <= register <= 0xFFFF:
        raise ValueError('Invalid Modbus register')
    signed = register - 65536 if register >= 32768 else register
    return signed / 1000.0
```

Example from PDF: `0xF6D7` = -2345 => -2.345 V on a voltage variant; `0x1168` = 4456 => 4.456 V.

For 4–20 mA sensors, 16.781 mA corresponds to register 16781, and engineering conversion is **separate**.

## Critical uncertainties

- The PDF shows 32-channel models but **does not enumerate AI16–AI31 registers**. Do not assume 0x0070–0x007F without manufacturer confirmation or controlled testing.
- No documented Modbus registers to change AI input range, calibration, IP, filtering, or sampling rate. Do not invent write operations.
- A table says FC03 reads conversion results and module information, but does not give module-information addresses.
