# Chengkong CK-DA08ETH — Cursor integration manuals

Source: `CK-DA08ETH Specifications Vr1.0`, manufacturer Shenzhen Chengkong Electronics, 12 pages. This is an **8-channel analog OUTPUT** module, not an analog input module.

## Specifications (PDF p. 3, 5, 9)
- 8 independent analog outputs AO0–AO7; 12-bit DAC; accuracy ±0.2% of full-scale range (manufacturer statement).
- Supported output ranges listed: 0–20 mA, 4–20 mA, 0–5 V, 0–10 V, ±5 V, ±10 V, ±20 mA. Exact installed/configured range must be verified for each channel.
- Ethernet Modbus TCP and RS485 Modbus RTU; supply 10–30 V DC; <5 W; DIN35 mounting.
- Response <3 ms (manufacturer specification); voltage outputs max 10 mA; current outputs load <=400 ohms at 20 mA.

## Files
- `MODBUS_REGISTERS.md`: verified register map, function codes, examples.
- `VARIABLES.md`: suggested application variable model and scaling.
- `CONFIGURATION.md`: communications and unknowns.
- `WIRING_AND_SAFETY.md`: manufacturer terminal map and safety.
- `TESTING.md`: staged test plan.
- `CURSOR_INSTRUCTIONS.md`: rules for AI-assisted changes.

**Do not energize controlled machinery on the basis of a code example.** Source PDF p. 8 is authoritative for register map; p. 6 and 12 for terminals.
