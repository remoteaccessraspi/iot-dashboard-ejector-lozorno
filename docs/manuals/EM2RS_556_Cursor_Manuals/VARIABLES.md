# Premenné pre iot_dashboard

Zdroj: Leadshine EM2RS Series Modbus RS485 Stepper Drive User Manual V1.5 (2021-08-30), https://www.leadshine.com/upfiles/downloads/04bbeba0c8c1196dc41e7d54c811d7d9_1650879175499.pdf

| Premenná | Typ | Význam |
|---|---|---|
| `em2rs_connected` | bool | dostupnosť Modbus RTU |
| `em2rs_motion_state_raw` | uint16 | FC03 0x1003 |
| `em2rs_fault` | bool | bit0 stavového slova |
| `em2rs_enabled` | bool | bit1 |
| `em2rs_running` | bool | bit2 |
| `em2rs_command_complete` | bool | bit4 |
| `em2rs_homing_complete` | bool | bit6 |
| `em2rs_alarm_code` | uint16 | FC03 0x2203 |
| `em2rs_position_estimated_steps` | int | FC03 0x602C/0x602D (actual position, signed 32 bit); v programe `actual_position_steps`; počítadlo drivera, NIE skutočne meraná poloha |
| `em2rs_position_valid` | bool | false po reštarte alebo strate referencie |
| `em2rs_target_steps` | int | 0–600 po kalibrácii, len aplikačný limit |
| `em2rs_motion_enabled` | bool | default false, autorizácia fyzického pohybu |
| `em2rs_last_ok_utc` | datetime | posledná úspešná odpoveď |

Nepovažovať polohu reportovanú driverom za potvrdenie mechanickej polohy ventilu. Všetky údaje sú v jednotkách konkrétne nakonfigurovaného Pulse/revolution; **600 mechanických impulzov sa nesmie bez overenia zamieňať za 600 interných polohových jednotiek drivera**.
