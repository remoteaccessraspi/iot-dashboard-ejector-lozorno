# Chengkong CK-8082R — manuály pre Cursor
Zdroj: `CK-8082R Specifications-Vr1.0.pdf`, výrobca Chengkong, revízia Vr1.0.

8 diferenciálnych analógových vstupov; 24-bitový ADC, ale Modbus merané hodnoty poskytuje ako **16-bit signed**. RS485 Modbus RTU (nie Modbus TCP). Napájanie 10–30 V DC; spotreba <2 W. Rozsahy podľa výrobcu ±20 mA, ±100 mV, ±1 V, ±2.5 V, ±5 V, ±10 V; konkrétny rozsah a osadenie prúdového odporu treba overiť pre daný kus.

## Súbory
- `MODBUS_REGISTERS.md` — overené čítacie registre
- `VARIABLES.md` — pomenovanie, prevody, kvalita dát
- `CONFIGURATION.md` — RTU a adresovanie
- `WIRING_AND_SAFETY.md` — svorky a bezpečnosť
- `TESTING.md` — postup skúšok bez zápisu
- `CURSOR_INSTRUCTIONS.md` — pravidlá pre implementáciu

## Zásada
Žiadny nezdokumentovaný zápis registrov. Hodnoty z manuálu a implementačné odporúčania sú odlíšené. Strany PDF uvádzame pri jednotlivých tvrdeniach.
