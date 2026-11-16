# CK-8082E — dokumentácia pre Cursor

Zdroj: `CK-8082E Specifications-Vr1.0.pdf`, Chengkong Electronics, 12 strán. Dokumentácia je určená na implementáciu do Raspberry Pi / Python / Modbus.

## Zariadenie
- 8 diferenciálnych analógových vstupov, interný 24-bitový ADC; presnosť podľa výrobcu ±0,05 % FS.
- Ethernet: Modbus TCP, dva porty na kaskádovanie; RS485: Modbus RTU.
- Napájanie 10–30 V DC, príkon <2 W, DIN35.
- V Modbus registroch sa napriek 24-bit ADC prenáša **16-bit signed** hodnota s mierkou 1000.

## Postup
1. Skontrolovať variant modulu pre mA alebo V (hardvérovo kalibrovaný pri objednávke).
2. Overiť IP/port alebo sériové parametre na konkrétnom zariadení.
3. Čítať 8 holding registrov od adresy 96 (FC03).
4. Konvertovať int16 a deliť 1000; priradiť jednotku podľa variantu.
5. Až potom nastaviť fyzikálne škálovanie pre senzory a uložiť do DB.

## Súbory
`MODBUS_REGISTERS.md`, `VARIABLES.md`, `CONFIGURATION.md`, `WIRING_AND_SAFETY.md`, `TESTING.md`, `CURSOR_INSTRUCTIONS.md`.

**Neznáme:** manuál neuvádza predvolenú IP, TCP port, Modbus TCP Unit ID, ani register na konfiguráciu rozsahu. Nepredpokladať ich ako overené údaje.
