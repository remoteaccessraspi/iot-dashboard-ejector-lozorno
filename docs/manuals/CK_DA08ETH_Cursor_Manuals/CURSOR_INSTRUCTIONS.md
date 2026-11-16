# Cursor agent instructions — CK-DA08ETH

Read **all files in this folder** before editing integration code. Device source is Chengkong `CK-DA08ETH Specifications Vr1.0` (12 pages).

1. This module is **8 analog outputs**, not inputs. Use AO0–AO7 with zero-based holding-register offsets `0x0040–0x0047`.
2. FC03 reads commanded values; FC06 writes one register; FC16 writes multiple. Register values are signed 16-bit engineering units ×1000.
3. Use actual configured channel range and units. Reject out-of-range values; never silently clamp or convert 4–20 mA to a percentage without explicit specification.
4. Do not invent network defaults, range-configuration registers, failsafe registers, startup state, or watchdog behavior. Request verified device information where needed.
5. On initial integration, implement **read-only** diagnostics. Writes remain disabled until the operator approves testing with an isolated load.
6. Inspect existing `iot_dashboard` Modbus abstraction, DB schema, YAML settings, HMI routes and 5-second scheduler before proposing edits. Do not create a second polling loop if one exists.
7. Keep setpoint, readback, physical measurement (if separately available), communication quality and timestamps distinct.
8. Avoid writing all eight channels during initialization. Do not send an arbitrary zero value to a 4–20 mA channel.
9. Provide unit tests for signed encoding, scaling, range checks and 0-based addressing. Add timeout/retry behavior without uncontrolled repeated writes.
10. Before any code change, summarize affected files, assumptions and safety implications; do not execute writes against physical hardware automatically.

### Suggested task for Cursor
> Read `docs/CK_DA08ETH/`. Inspect the existing project and propose a read-only Modbus TCP driver that reads AO0–AO7 via FC03 every 5 seconds, with verified configuration supplied externally. Add tests; do not write to the device.
