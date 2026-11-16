# Verification and commissioning

## 1. Offline
1. Confirm exact label `CK-DA08ETH`, installed output hardware, supply and firmware.
2. Confirm each channel's configured output type and physical range with manufacturer/test evidence.
3. Check scaling tests: 6.67 mA -> 6670, 8.65 V -> 8650, -5 V -> signed -5000 (`0xEC78`).
4. Confirm register offsets 64–71 (zero-based) and function codes FC03/FC06/FC16.

## 2. Non-actuating communications
1. Isolate outputs from live process equipment; use a safe bench load.
2. Connect TCP to **verified** IP/port or RTU 9600 8N1 address 1 (verify selector).
3. Read FC03 from `0x0040`, count 8; log raw values and timestamps.
4. If read fails, diagnose physical wiring, addressing, serial settings and network before writing.

## 3. Controlled output test — only after approval
1. Confirm load type and resistance, meter range, and emergency isolation.
2. Enable writes explicitly for **one channel**; set a safe permitted engineering value.
3. Use FC06 at the channel's register; read back FC03; measure actual voltage/current with an external instrument.
4. Test boundary setpoints only if the connected load is rated for them.
5. Record physical output versus commanded value and note the device's actual startup/loss-of-comms behavior as observations, not assumed guarantees.

## 4. Project integration
- Integrate FC03 readback into Raspberry Pi 5-second telemetry tick.
- Write setpoints only through authenticated/authorized control logic; retain last-known desired/readback and fault quality separately.
- Never equate register readback with measured analog output.
