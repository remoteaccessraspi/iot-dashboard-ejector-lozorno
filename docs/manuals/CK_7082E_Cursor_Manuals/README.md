# Chengkong CK-7082E — manuály pre Cursor

Zdroj: `CK-7082E Specifications-Vr1.1.pdf`, výrobca Chengkong Electronics, verzia Vr1.1, str. 3–12.

## Zariadenie
- 8 diferenciálnych analógových vstupov, 16-bit ADC; typická presnosť ±0,1 % (str. 3, 9).
- Varianty vstupných rozsahov podľa dodaného hardvéru: 0–20 mA, 4–20 mA, ±20 mA, 0–5 V, 0–10 V, ±5 V, ±10 V (str. 3); str. 5 uvádza navyše ±100 mV — overiť konkrétny variant.
- Modbus TCP cez dva kaskádovateľné ethernetové porty a Modbus RTU cez RS485 (str. 7–8).
- Napájanie 10–30 V DC; spotreba <2 W; DIN35 (str. 3, 10).

## Integrácia
Čítaj `MODBUS_REGISTERS.md`, `VARIABLES.md`, `CONFIGURATION.md`, `WIRING_AND_SAFETY.md`, `TESTING.md` a `CURSOR_INSTRUCTIONS.md`.

**Nie je to CK-8082E:** CK-7082E má 16-bit ADC, CK-8082E 24-bit ADC (str. 3).
