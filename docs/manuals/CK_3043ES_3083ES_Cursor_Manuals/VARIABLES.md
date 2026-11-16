# Variables and mapping — suggested software contract

The names below are **our integration convention**, not register names specified by Chengkong.

| Name | Type | Meaning |
|---|---|---|
| `rtd_temp_0_c` … `rtd_temp_3_c` | float or null | CK-3043ES channels 0–3 |
| `rtd_temp_0_c` … `rtd_temp_7_c` | float or null | CK-3083ES channels 0–7 |
| `rtd_raw_0` … `rtd_raw_7` | int or null | Original 16-bit register data |
| `rtd_comm_ok` | bool | Last Modbus request succeeded |
| `rtd_last_success_utc` | datetime or null | Timestamp of last successful poll |
| `rtd_error` | str or null | Latest communication/validation error |

Example YAML **application-level configuration**, not device registers:

```yaml
rtd_module:
  enabled: true
  model: CK-3083ES
  protocol: tcp   # tcp | rtu
  host: 192.168.1.30
  port: 502       # standard Modbus TCP port; confirm on device
  unit_id: 1
  poll_interval_s: 5
  first_register: 2
  channel_count: 8
  scale_c_per_count: 0.1
  timeout_s: 2
```

## Decoder

```python
def signed16(raw: int) -> int:
    if not 0 <= raw <= 0xFFFF:
        raise ValueError('Not a 16-bit register')
    return raw - 0x10000 if raw & 0x8000 else raw

def decode_temperature_c(raw: int) -> float:
    return signed16(raw) / 10.0
```

Keep register index and physical sensor label separately configurable. On communication error, set current measurement to null/invalid and do not silently reuse an old value as current.
