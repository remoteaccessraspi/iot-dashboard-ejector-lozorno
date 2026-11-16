# Network and device configuration

Manufacturer Vr1.1 pp. 2, 8, 10:
- Factory IP: `192.168.1.30`; TCP port `502`.
- Modbus TCP server (slave), function 03 reads measurements.
- Ethernet: two RJ45 ports, 10/100 Mbps, cascading supported; AUTO MDI-X noted.
- Supply 10–30 VDC (24 V nominal), consumption 2 W.
- Operating temperature −35 to +75 °C, humidity 5–95% noncondensing, IP20.
- LEDs: PWR blue powered, COM yellow flashes on communication, RUN blue flashes when program runs, ERR red indicates fault.

## Deployment settings
- Configure each device with a unique IP before connecting multiple factory-default units to one LAN.
- Keep network address, model, channel count, polling interval and timeouts configurable, never hardcode them in driver.
- Manufacturer does not specify in this PDF how IP changes, DHCP, reset behavior, simultaneous clients, or persistence of writes work. Confirm separately before implementation.
- Use one client per module initially; collect measurements into existing 5 s acquisition tick; avoid assumptions about multi-client capacity.
