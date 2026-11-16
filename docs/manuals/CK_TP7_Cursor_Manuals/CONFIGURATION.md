# Communications and device configuration

Source PDF pp. 2, 7–8.

- Modbus TCP server, factory default `192.168.1.30:502`.
- 2 × RJ45, 10/100 Mbps, Ethernet cascading.
- 10–30 V DC power, nominal 24 V DC, 2 W.
- Variant and electrical range selected at factory; do not infer a software-selectable 4–20 mA/voltage mode.

Recommended Raspberry Pi integration settings (project defaults, **not manufacturer specifications**):

```yaml
modbus_tcp:
  host: 192.168.1.30
  port: 502
  unit_id: 1
  timeout_seconds: 2
  retries: 2
  poll_interval_seconds: 5
  read_function: 3
  start_address: 96
  register_count: 8  # CK-TP7082; 16 for CK-TP7160
```

Before connecting multiple modules, assign unique IPs by a **manufacturer-verified** method. The provided PDF does not explain how to change IP or Unit ID. Do not execute undocumented reset/configuration commands.

A network timeout must not be interpreted as 0 mA, 0 V or a valid process zero. Preserve last good value separately and mark it STALE.
