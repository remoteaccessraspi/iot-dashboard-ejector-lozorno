# Wiring and electrical constraints

**Source:** Vr1.0 pp.6–7, 11, 14.

## RTD 3-wire wiring
For channel `n`: `Sn` receives the **single-colored wire**; the two same-colored wires go to `Dn` and `Dn`. Confirm the actual RTD lead colors with the sensor supplier, not by assuming a universal color scheme.

| Channel | S terminal | D terminal 1 | D terminal 2 |
|---|---:|---:|---:|
| 0 | 1 | 2 | 3 |
| 1 | 4 | 5 | 6 |
| 2 | 7 | 8 | 9 |
| 3 | 10 | 11 | 12 |
| 4 (3083ES only) | 17 | 18 | 19 |
| 5 (3083ES only) | 20 | 21 | 22 |
| 6 (3083ES only) | 23 | 24 | 25 |
| 7 (3083ES only) | 26 | 27 | 28 |

On CK-3043ES, terminals 17–32 are NC (p.7). Terminals 13–16 and 29–32 are NC on CK-3083ES.

## Power and bus
- Pin 33: `VIN`, +10 to +30 V DC.
- Pin 34: `GND`, supply ground.
- Pin 35: `B`, RS485 negative.
- Pin 36: `A`, RS485 positive.
- Pins 37–38: NC.
- 2 Ethernet sockets (cascading).

The manufacturer states channel isolation and 2000 V DC isolation withstand voltage (pp.3, 11); do not interpret this as permission to connect mains to RTD terminals.

**Safety:** isolate power before wiring, check polarity, prevent shorts, and verify actual terminal printing against pp.7 and 14. Use suitable industrial DC supply. Sensor-open detection is claimed, but its numeric Modbus representation is **not documented**.
