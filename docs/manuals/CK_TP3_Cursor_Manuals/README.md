# Chengkong CK-TP3XXX — Cursor integration manuals

Source: `CK-TP3 Series Temperature Specifications-Vr1.1-1.pdf`, manufacturer Vr1.1 (12 pages). This package is a source-grounded engineering reference, **not tested hardware behavior**.

## Supported models (manufacturer p.2)
| Model | Sensor | Channels |
|---|---|---:|
| CK-TP3043 | PT100 | 4 |
| CK-TP3045 | PT1000 | 4 |
| CK-TP3049 | Thermocouple K/T/J | 4 |
| CK-TP3083 | PT100 | 8 |
| CK-TP3085 | PT1000 | 8 |
| CK-TP3089 | Thermocouple K/T/J | 8 |
| CK-TP3169 | Thermocouple K/T/J | 16 |

Read `MODBUS_REGISTERS.md`, `WIRING_AND_SAFETY.md`, and `CURSOR_INSTRUCTIONS.md` before implementation. Do not reuse CK-TP7 analog-input register mappings or scaling.
