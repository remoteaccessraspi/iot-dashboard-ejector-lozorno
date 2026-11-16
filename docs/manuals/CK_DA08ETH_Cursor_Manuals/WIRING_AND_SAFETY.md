# Wiring, electrical limits and safe operation

Manufacturer PDF p. 3, 6, 9, 12. Check printed terminal labels before connecting.

## Terminals (PDF p. 6)
| Pin | Function |
|---:|---|
| 1 | AGND for AO0 |
| 2 | AO0+ |
| 3 | AGND for AO1 |
| 4 | AO1+ |
| 5 | AGND for AO2 |
| 6 | AO2+ |
| 7 | AGND for AO3 |
| 8 | AO3+ |
| 9 | AGND for AO4 |
| 10 | AO4+ |
| 11 | AGND for AO5 |
| 12 | AO5+ |
| 13 | AGND for AO6 |
| 14 | AO6+ |
| 15 | AGND for AO7 |
| 16 | AO7+ |
| 17 | VIN, positive 10–30 V DC |
| 18 | GND, supply negative |
| 19 | B, RS485 negative |
| 20 | A, RS485 positive |
| 21 | NC |
| 22 | NC |

For each channel, connect the controlled input between AOx+ and the associated AGND; verify voltage/current mode and polarity (p. 6).

## Limits
- Current-output load: external impedance <=400 Ω at 20 mA.
- Voltage-output current: <=10 mA.
- Do not connect a voltage-mode output to a low-impedance current input or vice versa without confirming specifications.
- Power off before rewiring; avoid connecting field supply voltage to analog outputs.
- Isolation withstand 2500 V DC is a manufacturer test rating, **not** permission to connect mains.

## Operational safety
- An analog output can actuate valves, drives or heaters: require explicit operator authorization and a safe physical test setup.
- Manual does **not** define what happens to outputs on power loss, network loss, watchdog timeout, or reboot. Treat fail-safe behavior as **unknown** and provide external safety interlocks where necessary.
- Do not infer that a documented 1-second watchdog period (PDF p. 9) provides a configurable communications failsafe.
