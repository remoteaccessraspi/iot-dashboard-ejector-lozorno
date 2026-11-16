# Chengkong CK-3043ES / CK-3083ES — Cursor integration manuals

Source: `CK-3043ES-3083ES Specifications-Vr1.0.pdf` (manufacturer, Vr1.0, 14 pages). This package is a transcription-oriented implementation guide, **not** a replacement for hardware verification.

| Model | RTD channels | Interfaces | Sensor type |
|---|---:|---|---|
| CK-3043ES | 4 | RS485 + 2 Ethernet cascade ports | PT100/PT1000 |
| CK-3083ES | 8 | RS485 + 2 Ethernet cascade ports | PT100/PT1000 |

16-bit ADC; typical accuracy ±0.5 °C; DC 10–30 V; DIN35. Manufacturer p.3 lists 25 full-channel conversions/s for CK-3043ES and 50/s for CK-3083ES. Both support Modbus RTU/TCP.

## Files
- `MODBUS_REGISTERS.md` — verified temperature addresses, conversions and ambiguities.
- `VARIABLES.md` — recommended Python/YAML variable names.
- `CONFIGURATION.md` — communication and IP settings.
- `WIRING_AND_SAFETY.md` — 3-wire RTD terminals and power.
- `TESTING.md` — non-destructive tests.
- `CURSOR_INSTRUCTIONS.md` — binding instructions for code assistant.

**Scope:** documentation for reading temperatures; no undocumented configuration-register writes.
