# Network and serial configuration

**Manufacturer source:** Vr1.0 pp.8–10.

## Modbus RTU / RS485
- Factory station address **1** (allowed 1–247).
- Default **9600 baud, 8 data bits, no parity, 1 stop bit**.
- Listed baud rates: 1200, 2400, 4800, 9600, 14400, 19200, 115200 bps.
- RS485 terminals: B = negative, A = positive (p.7).
- Use bus topology, short stubs, and appropriate termination for long lines (p.8).

## Modbus TCP / Ethernet
- Two RJ45 ports for Ethernet cascading; manufacturer says 10/100 Mbit/s and AUTO-MDIX.
- Factory **DHCP OFF**, **IP 192.168.1.30**, **mask 255.255.255.0**, **gateway 192.168.1.1** (p.10).
- Standard Modbus TCP port **502** is a conventional client default, **not explicitly confirmed by this PDF**; verify on device.
- When DHCP is enabled, static menu IP is ignored; router assigns address.
- Network settings become effective **after restart/power cycle** (p.10).

## Settings workflow
Manufacturer describes an OLED menu on **some** CK series models (p.10), not unequivocally for every CK-3043ES/3083ES variant. If the actual module has a menu, configure address/IP there. The PDF does **not** give reliable Modbus configuration register addresses. Do not write guessed registers.

## Raspberry Pi integration
Use one polling owner per physical connection. A 5-second acquisition cycle is an application choice and comfortably slower than the stated conversion rates. Handle timeouts, reconnections, and per-device status independently. For Modbus TCP, verify Unit ID behavior on the actual hardware.
