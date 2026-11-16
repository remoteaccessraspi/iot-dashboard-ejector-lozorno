# Leadshine EM2RS-556 — dokumentácia pre Cursor

Zdroj: Leadshine EM2RS Series Modbus RS485 Stepper Drive User Manual V1.5 (2021-08-30), https://www.leadshine.com/upfiles/downloads/04bbeba0c8c1196dc41e7d54c811d7d9_1650879175499.pdf

## Účel
Riadenie krokového motora expanzného ventilu ETS 12C cez Raspberry Pi / Modbus RTU. Driver nie je Modbus TCP zariadenie.

- Napájanie drivera 20–50 V DC, maximálny špičkový prúd 5,6 A (str. 7, 13 PDF).
- Modbus RTU: FC03, FC06, FC16 (v manuáli označené 0x10).
- Režimy Profile Position, Profile Velocity, Homing, interná 16-polohová PR tabuľka.
- 7 DI, 3 DO; RS485 CN4, servisný RS232 CN5.

## Projektové predpoklady (nie parametre výrobcu)
ETS 12C: 600 impulzov/3 otáčky na plný zdvih, 50 rpm, referenčný pohyb 650 impulzov k mechanickému dorazu. Bez enkódera a bez koncových spínačov. Tieto údaje treba pred použitím fyzicky potvrdiť.

## Poradie čítania
MODBUS_REGISTERS.md → VARIABLES.md → CONFIGURATION.md → MOTION_CONTROL.md → SAFETY.md → TESTING.md → CURSOR_INSTRUCTIONS.md.
