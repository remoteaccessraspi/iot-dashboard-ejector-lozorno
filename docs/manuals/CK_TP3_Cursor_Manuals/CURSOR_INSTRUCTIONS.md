# Cursor task — integrate CK-TP3 temperature modules into Raspberry Pi project

## Scope
Implement a modular, nonblocking Modbus TCP **temperature acquisition driver** for Chengkong CK-TP3XXX, following this documentation. Inspect existing repository patterns first; do not overwrite unrelated devices, database schemas or HMI functionality.

## Requirements
1. Configurable device model, IP, TCP port (default 502), unit ID (example uses 1), timeout and polling interval (project currently uses 5 s).
2. Use FC03; read channel 0 at zero-based address 2. For each channel, decode 16-bit signed and divide by 10 to °C.
3. Model-aware channel limits; mark TP3083/3085 CH4–CH7 as `requires_hardware_verification` until tested, rather than hard-failing or claiming documented support.
4. Keep raw word, decoded °C, timestamp, validity and communication errors. Stale measurements must not be treated as current.
5. Default read-only. Never write `0x0580..0x058F` unless a separate explicit configuration operation is approved; E-type TC remains unsupported pending validation.
6. Add mock Modbus tests using `TESTING.md` examples. Avoid real hardware writes in tests.
7. Reuse existing database/HMI architecture and 5 s scheduler; avoid blocking other acquisition devices on timeout.
8. Report any undocumented device behavior rather than guessing.

## Suggested rollout
- Stage A: driver + offline tests.
- Stage B: single device bench verification with logs.
- Stage C: DB/HMI integration, status alarms, reconnect tests.
- Stage D: multi-device commissioning and documentation update.

## Source limitations to surface in code comments
- Manufacturer p.9 CH4–CH7 RTD inconsistency.
- Manufacturer p.9 E thermocouple code vs p.2 K/T/J specification.
- IP setup method, special sensor fault codes, accuracy, sampling rate, and concurrent client limits not specified.
