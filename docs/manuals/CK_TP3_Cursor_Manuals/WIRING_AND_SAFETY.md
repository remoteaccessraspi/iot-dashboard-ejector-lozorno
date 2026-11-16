# Terminals, wiring and electrical safety

Manufacturer Vr1.1 pp.5–7, 10. **Use the physical terminal diagrams on pp.5–7 as the wiring authority.**

## Power/network
- Power terminal 1 = `24V` positive, 2 = `0V` negative, 3 = `PE` protective earth (p.5).
- Two RJ45 Ethernet connectors; do not mistake them for sensor inputs.
- Supply 10–30 VDC; IP20, DIN35 mounting.

## RTD models
- 4-channel models CK-TP3043 (PT100) and CK-TP3045 (PT1000):
  - CH0: terminals 1=`S0`, 2=`D0`, 3=`D0`.
  - CH1: 4=`S1`, 5=`D1`, 6=`D1`.
  - CH2: 9=`S2`, 10=`D2`, 11=`D2`.
  - CH3: 12=`S3`, 13=`D3`, 14=`D3`.
  - 7/8/15/16 NC.
- 8-channel models CK-TP3083/3085: first connector as above; second connector:
  - CH4: 17=`S4`, 18/19=`D4`.
  - CH5: 20=`S5`, 21/22=`D5`.
  - CH6: 25=`S6`, 26/27=`D6`.
  - CH7: 28=`S7`, 29/30=`D7`.
  - 23/24/31/32 NC.
- Diagram on p.7 shows **three-wire RTD wiring**. Two-wire sensor connection and compensation are not documented; do not invent a jumper scheme.

## Thermocouple models
- CK-TP3049: CH0..3 positive terminals 1..4 and negative terminals 9..12.
- CK-TP3089: CH0..7 positive terminals 1..8 and negative terminals 9..16.
- CK-TP3169: CH0..7 as above; CH8..15 positive terminals 17..24 and negative terminals 25..32 (p.6 uses hex-style A..F for channels 10..15).
- Respect polarity and thermocouple alloy/cable requirements. Cold-junction accuracy and wiring compensation are not quantified in this PDF.

## Safety and testing
- Manufacturer recommends conductor cross section ≤1 mm² and strip length 10–12 mm (p.7).
- Never wire or rewire powered terminals; check supply polarity and protective grounding.
- The datasheet cites DC 2500 V isolation and ±15 kV ESD protection (p.2), not permission to connect arbitrary hazardous potentials.
