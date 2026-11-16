# Premenné GD20 v programe

Názvy vľavo sú tie, ktoré číta a zapisuje `iot_core/devices/invt_gd20.py` a ukladá do `invt_gd20_state` alebo `control_state`.

| Názov v programe | Jednotka | Register |
|---|---|---|
| `gd20_setpoint_kpa` | kPa | žiadaná hodnota z HMI; zápis na `0x2002` po prevode 0–1500 kPa → 0–1000 |
| `pid_setpoint_kpa` | kPa | čítanie `0x3008`, percentá prepočítané na 0–1500 kPa |
| `pid_feedback_kpa` | kPa | čítanie `0x3009`, rovnaký prepočet |
| `ai2_kpa` | kPa | čítanie `0x300D`; alias v YAML `p_gen_prim_from_frq` |
| `frequency_actual_hz` | Hz | čítanie `0x3000` |
| `frequency_set_hz` | Hz | čítanie `0x3001`, nie zápisový register `0x2001` |
| `dc_bus_voltage_v` | V | čítanie `0x3002` |
| `output_voltage_v` | V | čítanie `0x3003` |
| `output_current_a` | A | čítanie `0x3004` |
| `motor_speed_rpm` | rpm | čítanie `0x3005` |
| `status_code` | uint16 | čítanie `0x2100` |
| `running` | bool | `status_code` je 1 alebo 2 |
| `fault_code` | uint16 | čítanie `0x5000` |
| `external_stop` | bool | `0x300A` bit3 |
| `gd20_run` | `1` / `0` | príkaz HMI; zapíše sa ako `0x2000` = `0x0001` alebo `0x0005` |

`0x3006` a `0x3007` program prečíta, lebo ležia v súvislom bloku, a do databázy ich neukladá.
