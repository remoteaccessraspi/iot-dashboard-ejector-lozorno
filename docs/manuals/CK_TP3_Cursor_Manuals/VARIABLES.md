# Application variables and data model

Suggested application schema (integration proposal; **not** manufacturer-defined):

| Variable | Type | Meaning |
|---|---|---|
| `device_id` | string | Stable local ID |
| `model` | enum | Exact CK-TP3 model |
| `ip_address` | string | Configured IP |
| `port` | int | Default 502 |
| `channel_count` | int | 4, 8 or 16 |
| `sensor_type` | enum | PT100, PT1000, TC_K, TC_J, TC_T |
| `temperature_c[n]` | float/null | Decoded °C |
| `raw_register[n]` | uint16/null | Raw word, for diagnostics |
| `valid[n]` | bool | Valid fresh sample |
| `last_success_utc` | timestamp | Last successful read |
| `communication_error` | string/null | Timeout, disconnect, Modbus exception |

Keep raw words alongside decoded temperatures. Decode signed 16-bit before dividing by ten. A failed read must not silently reuse a stale temperature as fresh data. Attach timestamps to all records; expose status in HMI.

Example conversion (Python):
```python
def decode_temperature_c(raw_u16: int) -> float:
    if not 0 <= raw_u16 <= 0xFFFF:
        raise ValueError('Expected 16-bit register')
    signed = raw_u16 - 65536 if raw_u16 >= 32768 else raw_u16
    return signed / 10.0
```
