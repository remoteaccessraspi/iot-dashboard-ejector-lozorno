# Chengkong CK-TP7XXX — Cursor manuals

Source: `CK-TP7 Series Analog Specifications-Vr1.1-1.pdf`, Chengkong Electronics, Vr1.1, 10 pages.

Applies to CK-TP7082 (8 AI), CK-TP7160 (16 AI), CK-TP7320 (32 AI). Variants I1: 4–20 mA / ±20 mA; I6: 0–10 V / ±10 V; I5: 0–5 V / ±5 V. Input range is **factory preset**: do not assume software-selectable ranges.

Files: `MODBUS_REGISTERS.md`, `VARIABLES.md`, `CONFIGURATION.md`, `WIRING_AND_SAFETY.md`, `CURSOR_INSTRUCTIONS.md`, `TESTING.md`.

**Key point:** Modbus TCP FC03, holding-register offsets 0x0060 onward; values signed int16 / 1000 in mA or V, **not engineering units of the connected process**. Sensor scaling must be configured separately.

The PDF explicitly documents only AI0–AI15 register addresses. For CK-TP7320 AI16–AI31, register addresses are **not verified** and must not be guessed.
