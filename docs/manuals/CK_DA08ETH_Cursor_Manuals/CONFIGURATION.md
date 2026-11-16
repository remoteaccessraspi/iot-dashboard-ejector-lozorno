# Communications and configuration

Manufacturer PDF p. 3, 7–8.

## RS485 Modbus RTU
- Factory defaults: address `1`, `9600 baud`, `8N1` (p. 8).
- Supported baud rates: 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200.
- Software-address range 1–247; two-digit mechanical address selector range 1–99.
- Selector `00`: use software-stored address; nonzero: use selector address; selector changes take effect at next power-on/restart.
- Selector affects serial address, **not Ethernet**.

## Ethernet Modbus TCP
- One Ethernet port, supports Modbus TCP (p. 7).
- **Default IP, TCP port, Unit ID, IP configuration method and network recovery procedure are not specified in the supplied PDF.** TCP port 502 is a common Modbus default but **must be verified on this hardware**.
- Record the actual IP and port in deployment configuration; do not hardcode guessed defaults.

## Example project configuration (not factory defaults)
```yaml
ck_da08eth:
  enabled: false
  protocol: tcp
  host: null       # set from verified device configuration
  port: 502        # conventional Modbus TCP port; verify
  unit_id: 1       # verify for TCP
  poll_seconds: 5
  writes_enabled: false
  channels:
    ao0:
      range: null  # e.g. '4-20mA', verify physical configuration
      safe_setpoint: null
```

Five-second polling is a **project integration choice**, not a device requirement. Writes should be event-driven/controlled, not repeated blindly every poll.
