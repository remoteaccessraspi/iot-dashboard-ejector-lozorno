# Cursor rules — CK-TP7XXX analog modules

1. Read `README.md`, `MODBUS_REGISTERS.md`, `VARIABLES.md`, `CONFIGURATION.md`, and `WIRING_AND_SAFETY.md` before implementation.
2. Inspect the existing `iot_dashboard` Modbus client, 5 s polling scheduler, DB schema, and HMI before editing; reuse existing conventions.
3. Use FC03 for analog readings. Only read documented AI0–AI15 at offsets 96–111. Limit register count to installed model (8 for 7082, 16 for 7160).
4. For 7320, AI16–AI31 addresses are UNKNOWN; stop and request confirmation, do not extrapolate.
5. Decode each register as signed int16, divide by 1000. Unit is mA for I1 and V for I5/I6; actual factory range must be verified.
6. Scale electrical values to physical process values only using explicitly configured transducer range, units and calibration.
7. Preserve raw values and quality/status. Never convert communication failure to zero or reuse stale readings as current.
8. No writes to undocumented Modbus addresses. No changes to live plant hardware without explicit approval.
9. Use one polling owner per device where practical; prevent overlapping reads; expose data to HMI/DB via existing project interfaces.
10. Keep testable decoding/scaling logic separate from network I/O. Add tests for positive/negative signed values, missing responses, range and model constraints.
11. Do not confuse PLC 40097 with zero-based protocol offset 96. In pymodbus, check installed library API before implementing.
12. For documentation gaps, explicitly mark UNKNOWN rather than guessing.

## Cursor task prompt

> Analyze the current iot_dashboard architecture and propose CK-TP7XXX Modbus TCP read-only integration according to these manuals. First produce a file-by-file change plan, register mapping, sensor configuration schema, quality handling, and tests. Do not write to the device or change running services until approved.
