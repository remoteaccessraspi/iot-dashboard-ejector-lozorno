# Premenné a škálovanie

## Štandardné názvy

| Premenná | Typ | Jednotka | Popis |
|---|---|---|---|
| `ck8082e_ai0_raw` až `ck8082e_ai7_raw` | uint16 | — | pôvodná hodnota Modbus |
| `ck8082e_ai0_signal` až `ck8082e_ai7_signal` | float | mA alebo V | dekódovaný signál |
| `ck8082e_ai0_value` až `ck8082e_ai7_value` | float/null | podľa snímača | fyzikálna hodnota |
| `ck8082e_online` | bool | — | úspešná komunikácia |
| `ck8082e_last_ok_utc` | datetime/null | UTC | posledné úspešné čítanie |
| `ck8082e_quality` | enum | — | GOOD / TIMEOUT / MODBUS_ERROR / INVALID_CONFIG |

## Konfigurácia jednotlivých kanálov

```yaml
ck8082e:
  enabled: false
  transport: tcp  # tcp alebo rtu
  tcp:
    host: null     # nutné vyplniť podľa reálneho zariadenia
    port: 502      # štandardný port Modbus TCP, NIE potvrdený manuálom
    unit_id: 1     # príklad, pre TCP treba overiť
  rtu:
    port: /dev/ttyUSB0  # príklad, overiť na Raspberry Pi
    baudrate: 9600
    bytesize: 8
    parity: N
    stopbits: 1
    slave_id: 1
  polling_seconds: 5
  channels:
    - {index: 0, enabled: false, signal_type: null, sensor_min: null, sensor_max: null, engineering_unit: null}
```

`signal_type` musí byť napr. `4-20mA`, `0-10V`, `+-10V` až po overení hardvéru. Rozšíriť konfiguráciu na AI1–AI7. Bez konfigurácie senzora nezapisovať odhadované fyzikálne hodnoty.

## Škálovanie 4–20 mA (iba príklad)
`engineering = min + (mA - 4) * (max - min) / 16`. Rozsah snímača nie je v manuáli uvedený; zadať samostatne. Rozlišovať výpadok slučky a hodnotu mimo rozsahu podľa požiadaviek konkrétnej aplikácie.
