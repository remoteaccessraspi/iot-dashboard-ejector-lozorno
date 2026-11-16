# Modbus register map — CK-DA08ETH

Source: manufacturer's Vr1.0 PDF p. 8–9.

| Channel | Zero-based Modbus register (hex) | Decimal offset | PLC-style holding register |
|---|---|---:|---:|
| AO0 | `0x0040` | 64 | 40065 |
| AO1 | `0x0041` | 65 | 40066 |
| AO2 | `0x0042` | 66 | 40067 |
| AO3 | `0x0043` | 67 | 40068 |
| AO4 | `0x0044` | 68 | 40069 |
| AO5 | `0x0045` | 69 | 40070 |
| AO6 | `0x0046` | 70 | 40071 |
| AO7 | `0x0047` | 71 | 40072 |


## Supported functions (PDF p. 8)
- FC03: read output **setpoint**, not independent analog measurement or feedback.
- FC06: write one holding register.
- FC16 (`0x10`): write multiple holding registers.
- The manual writes `06/10` in hexadecimal notation; `0x10` means decimal function code **16**, not decimal 10.

## Scaling
- Each register is a **signed 16-bit integer**, representing the actual engineering output quantity ×1000, according to the channel's configured physical range.
- `raw = round(value_mA_or_V * 1000)`; `value_mA_or_V = int16(raw)/1000`.
- Example: 6.67 mA -> 6670; 8.65 V -> 8650 (PDF p. 8).
- Negative setpoints use two's-complement signed 16-bit encoding; e.g. -5.000 V -> -5000 -> unsigned transport word 60536 (`0xEC78`).
- **Not** a DAC code in the 0–4095 range; 12 bits describes converter resolution, not the register representation.

## RTU example (PDF p. 9)
- Write four registers from `0x0040` with FC16; raw words 6892, 5653, 11258, 17539 correspond to 6.892, 5.653, 11.258, 17.539 mA.
- Example in PDF uses a four-channel demonstration; actual CK-DA08ETH has eight channels.

## Not specified
- No documented holding registers for output-range selection, IP assignment, failsafe defaults, watchdog settings, calibration, or EEPROM persistence. Do **not** invent them.
- The PDF does not establish that reading back the setpoint proves the physical analog output is correct.
