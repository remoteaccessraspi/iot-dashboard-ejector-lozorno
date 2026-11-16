# Verification checklist — CK-TP3XXX

## Offline unit tests
1. Decode `0x0618` → `156.0 °C`, `0x03D9` → `98.5 °C`, `0x015A` → `34.6 °C`, `0x0315` → `78.9 °C` (p.9).
2. Decode signed negative raw `0xFE7B` (−389) → `−38.9 °C`.
3. Verify address CH0=2, CH3=5, CH7=9, CH15=17; reject out-of-model channels.
4. Verify no CK-TP7 scaling `/1000` leaks into CK-TP3 (`/10`).
5. Simulate Modbus exception, timeout, truncated response, disconnection; status invalid, no silent stale values.

## Hardware acceptance tests
- Record exact model, firmware if obtainable, serial and IP; confirm single module reachable on TCP 502.
- Read FC03 from address 2 with 4 registers; compare against independent temperature reference.
- For RTD TP3083/3085, **verify CH4–CH7 empirically**, since manufacturer register table has a contradiction.
- Test 3-wire RTD wiring and thermocouple polarity, at ambient and elevated temperature.
- If changing TC type via `0x0580+n`, read current value first, write only with explicit approval, read back and power-cycle to test persistence.
- Confirm open-sensor and short-circuit behavior before defining alarm thresholds.
- Run sustained polling at the project's 5 s tick and record disconnect/reconnect behavior.

## Acceptance evidence
Capture raw registers, decoded °C, timestamps, physical reference reading, exception logs, and firmware/model identification. Mark unverified claims as pending rather than assuming successful tests.
