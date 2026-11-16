# Application variables and conversions

These are **proposed software variable names**, not device-defined names. Source register/scaling details: PDF p. 8.

| Software name | Register | Unit | Type | Description |
|---|---|---|---|---|
| `ao0_setpoint` | `0x0040` | configured V or mA | float | Desired AO0 physical output |
| `ao1_setpoint` | `0x0041` | configured V or mA | float | Desired AO1 physical output |
| `ao2_setpoint` | `0x0042` | configured V or mA | float | Desired AO2 physical output |
| `ao3_setpoint` | `0x0043` | configured V or mA | float | Desired AO3 physical output |
| `ao4_setpoint` | `0x0044` | configured V or mA | float | Desired AO4 physical output |
| `ao5_setpoint` | `0x0045` | configured V or mA | float | Desired AO5 physical output |
| `ao6_setpoint` | `0x0046` | configured V or mA | float | Desired AO6 physical output |
| `ao7_setpoint` | `0x0047` | configured V or mA | float | Desired AO7 physical output |


Keep separately per channel: `aoN_range` (explicitly configured and verified range), `aoN_unit` (`V` or `mA`), `aoN_raw` (signed int16), `aoN_last_written`, `aoN_readback`, `aoN_write_enabled`, `aoN_quality`, `aoN_timestamp`.

## Encode/decode
```python
def encode_output(value: float, low: float, high: float) -> int:
    if not (low <= value <= high):
        raise ValueError('Output setpoint outside configured physical range')
    raw = round(value * 1000)
    if not -32768 <= raw <= 32767:
        raise ValueError('Value outside signed 16-bit range')
    return raw & 0xFFFF  # Modbus register word

def decode_output(word: int) -> float:
    signed = word - 65536 if word >= 32768 else word
    return signed / 1000.0
```

**Never assume** all channels share the same output range. Validate range before any write. Keep the user-facing engineering unit explicit. Avoid mapping the module to AI sensor values: it is an actuator.
