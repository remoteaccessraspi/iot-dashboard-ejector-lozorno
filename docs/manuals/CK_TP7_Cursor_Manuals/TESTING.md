# Verification checklist — CK-TP7XXX

## Offline tests

- `0x1168` -> 4.456; `0x1639` -> 5.689; `0x0926` -> 2.342; `0xF6D7` -> -2.345.
- 16781 -> 16.781 mA for current model.
- 4.0 mA -> configured process minimum; 20.0 mA -> configured process maximum.
- Read timeout -> COMM_ERROR / STALE, never a valid 0.
- CK-TP7082 rejects AI8+; CK-TP7160 rejects AI16+; CK-TP7320 AI16+ disabled pending register verification.

## Hardware commissioning (read-only)

1. Confirm exact model suffix, wiring and input type from label.
2. Confirm device IP is unique; default may be 192.168.1.30.
3. Confirm physical wiring and transducer power supply.
4. Read FC03 at 0x0060 for one channel, then a block matching the device.
5. Compare values against a known reference signal and independently measured process variable.
6. Validate negative readings where applicable, loss of signal, reconnection, and data timestamps.
7. Integrate 5-second polling only after measurements are confirmed.

No automatic network scanning, firmware writes, reset, or register writes are authorized by these manuals.
