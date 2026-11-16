# Variables, naming, scaling and quality

Use configuration-driven channels, not hard-coded sensor meanings.

| Field | Type | Meaning |
|---|---|---|
| `device_id` | str | Unique module instance |
| `model` | str | e.g. CK-TP7082I1 |
| `ip` | str | Device IPv4 |
| `port` | int | TCP port, default 502 |
| `unit_id` | int | Configured Modbus unit identifier |
| `channel` | int | AI index, zero-based |
| `register_offset` | int | 0x60 + channel for documented AI0–AI15 only |
| `raw_register` | int | Unsigned 16-bit word as received |
| `signed_count` | int | Signed 16-bit interpretation |
| `electrical_value` | float | signed_count / 1000 |
| `electrical_unit` | str | mA or V, based on factory hardware variant |
| `engineering_value` | float or null | Calibrated process quantity |
| `engineering_unit` | str | kPa, °C, L/min etc. |
| `quality` | str | GOOD, COMM_ERROR, OUT_OF_RANGE, STALE, UNCONFIGURED |
| `timestamp_utc` | str | Timestamp of successful read |

## Example sensor conversion (application-level, not a device register)

For a 4–20 mA sensor with process range `min_eng` to `max_eng`:

```python
def ma_to_engineering(ma, min_eng, max_eng):
    return min_eng + (ma - 4.0) * (max_eng - min_eng) / 16.0
```

For a 0–10 V sensor: `eng = min_eng + voltage / 10 * (max_eng - min_eng)`.

**Do not clamp** out-of-range readings silently. Flag and retain raw values; configure application thresholds, e.g. for broken 4–20 mA loops. Never assume all sensors have the same pressure/temperature range.

## Example YAML (application configuration, not vendor-native)

```yaml
devices:
  - id: ck_tp7082_01
    model: CK-TP7082I1
    ip: 192.168.1.30
    port: 502
    unit_id: 1
    channels:
      - index: 0
        name: pressure_1
        register_offset: 96
        electrical_unit: mA
        process_min: 0.0
        process_max: 1000.0
        engineering_unit: kPa
```

Process range `0–1000 kPa` above is **illustrative only** and must be replaced with the actual transducer datasheet.
