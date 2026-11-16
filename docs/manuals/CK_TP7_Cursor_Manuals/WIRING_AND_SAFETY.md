# Terminals, wiring and safety

Source PDF pp. 5–6, 8.

## Power/network

Power terminal 1 = +24 V (nominal), terminal 2 = 0 V, terminal 3 = PE. Supply permitted 10–30 V DC. Dual Ethernet ports for cascade.

## CK-TP7082 (8 AI)

- Terminals 1–8: AI0–AI7.
- Terminals 9, 10, 19, 20: AGND.
- Terminals 11–18: NC (do not connect).

## CK-TP7160 (16 AI)

- Terminals 1–8: AI0–AI7.
- Terminals 11–18: AI8–AI15.
- Terminals 9, 10, 19, 20: AGND.

The PDF includes two-, three-, and four-wire sensor wiring diagrams on page 6. Verify actual sensor pinout, supply, polarity and whether the specific hardware variant is current or voltage input before wiring. Inputs are single-ended; AGND is the analog reference. Do not assume galvanic isolation between individual channels.

## CK-TP7320

32 channels are advertised, but a full terminal pinout is **not provided** in this PDF. Obtain a dedicated wiring diagram before installation.

- Suggested conductor cross-section <= 1 mm² (manufacturer).
- Operating -35 to +75 °C; IP20; 5–95% RH without condensation.
- The manufacturer describes input overvoltage/overcurrent protection, but does not provide allowable absolute input overrange values. Never use this as justification to apply arbitrary voltage/current.
