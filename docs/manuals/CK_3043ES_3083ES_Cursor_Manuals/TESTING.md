# Non-destructive validation plan

1. Check nameplate: CK-3043ES (4 channels) or CK-3083ES (8 channels), and confirm PT100/PT1000 sensor variant.
2. With power disconnected, verify three-wire RTD connections and DC supply polarity against manufacturer pp.6–7,14.
3. Power up with DC 10–30 V. Check module status and actual Ethernet IP / RS485 settings.
4. For TCP, first test network reachability, then test a read-only FC03 transaction at offset 2; verify port 502 on hardware.
5. For RTU, test slave 1 at 9600 8N1 and read-only FC03 start 2, count 4/8.
6. Decode `int16 / 10`; compare each reading with a known reference thermometer, including negative values if available.
7. Disconnect a test sensor only under safe laboratory conditions and observe behavior; document the actual open-circuit response before introducing alarms.
8. Test network/serial disconnection, timeouts and recovery. Mark stale data invalid.
9. Check 5-second sampling with all active channels and logging to MariaDB; do not block the main polling loop indefinitely.
10. Never run output writes from the p.9 digital-output rows without manufacturer confirmation.

## Expected sample RTU frame (p.10)
Request: `01 03 00 02 00 04 E5 C9`
Response example: `01 03 08 06 18 03 D9 01 5A 03 15 70 CC`
Expected °C: `156.0, 98.5, 34.6, 78.9`.

**Acceptance:** valid temperature readings and reliable reconnection, with no unapproved device parameter changes.
