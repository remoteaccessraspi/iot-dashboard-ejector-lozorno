# Instructions for Cursor — CK-3043ES / CK-3083ES

Read all Markdown documents in this folder before changing code. The manufacturer's source of truth is `CK-3043ES-3083ES Specifications-Vr1.0.pdf`.

## Required behavior
1. Inspect existing `iot_dashboard` Modbus, config, database and HMI patterns first. Preserve the 5-second common acquisition tick.
2. Determine exact installed model; use 4 channels for CK-3043ES or 8 for CK-3083ES.
3. Read **holding registers** using FC03 from zero-based address **2** for 4/8 registers. Do not shift addresses by 1 or add 40001.
4. Convert each 16-bit register to **signed int16**, then divide by 10 for °C.
5. Provide configurable IP/serial port, Unit ID, timeout, sensor names, and channel enable flags; avoid hardcoding installation-specific identifiers.
6. Do not invent RTD configuration registers, broken-sensor codes or writable digital outputs. Flag unknowns and ask for hardware validation.
7. Separate read-only acquisition from any device configuration workflow. No writes to hardware without explicit approval.
8. Handle Modbus errors, reconnect, log errors at reasonable frequency and mark readings stale/invalid.
9. Propose unit tests for signed conversion, address mapping, 4/8-channel counts and communication failure.
10. Before edits, summarize target files, planned changes and risks. After edits, show tests and unresolved assumptions.

## Suggested task for Cursor
> Integrate CK-3083ES read-only temperature acquisition into the existing Raspberry Pi iot_dashboard project, following docs/CK_3043ES_3083ES. First inspect the current Modbus polling, MariaDB schema and YAML configuration. Propose changes before editing. No Modbus writes.

## Manufacturer caveats
The PDF p.9 includes digital-output rows inconsistent with the RTD-only wiring. Treat as unverified. The PDF p.10 discusses a menu on *some* CK models; do not assume this model exposes that UI. Port 502 is standard but not explicitly documented in the PDF.
