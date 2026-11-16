# Modbus TCP register map (manufacturer Vr1.1 p.9)

**Register addresses below are zero-based protocol addresses, not 4xxxx display labels.**

## Temperature readout
- Function `0x03` (Read Holding Registers).
- Channel `n` temperature at address `0x0002 + n`, for valid channels.
- Each result is signed 16-bit integer (two's complement); **temperature °C = signed_value / 10**.
- Examples given: `1678 → 167.8 °C`, `5089 → 508.9 °C`, `−389 → −38.9 °C`.

| Channel | Address hex | Decimal |
|---|---|---:|
| 0 | `0x0002` | 2 |
| 1 | `0x0003` | 3 |
| 2 | `0x0004` | 4 |
| 3 | `0x0005` | 5 |
| 4 | `0x0006` | 6 |
| 5 | `0x0007` | 7 |
| 6 | `0x0008` | 8 |
| 7 | `0x0009` | 9 |
| 8 | `0x000A` | 10 |
| 9 | `0x000B` | 11 |
| 10 | `0x000C` | 12 |
| 11 | `0x000D` | 13 |
| 12 | `0x000E` | 14 |
| 13 | `0x000F` | 15 |
| 14 | `0x0010` | 16 |
| 15 | `0x0011` | 17 |


**Source ambiguity:** p.9 explicitly marks channels 4–7 as “only TP3089/TP3169”, even though p.2 lists 8-channel RTD models TP3083/TP3085. Therefore channels 4–7 on 8-channel RTD models are **not confirmed by this register table**; bench-test before treating them as supported. Channels 8–15 are explicitly TP3169 only.

## Thermocouple type/range configuration
Manufacturer p.9 lists register `0x0580 + n` for channel `n` (n=0..15 where applicable), with functions `03/06/10` (read / write single / write multiple). Values: `26=K`, `27=J`, `28=T`, `31=E`.

**Important:** p.2/p.4/p.10 advertise K/T/J, while p.9 additionally lists E. E-type hardware support is **unverified**. Do not enable E without supplier confirmation and tests. The table labels these as channel “range”; applicability to RTD models is **not established**. Do not write these registers on RTD units without confirmation.

## Request example (manufacturer p.9)
Request to read 4 temperatures: `00 01 00 00 00 06 01 03 00 02 00 04` (MBAP transaction ID 1, unit ID 1, FC03, start 2, count 4).
Reply example: `00 01 00 00 00 0B 01 03 08 06 18 03 D9 01 5A 03 15`, decoding 156.0, 98.5, 34.6, 78.9 °C.

Do not assume exception values, sensor-disconnect sentinels, or measurement resolution beyond 0.1 °C are specified; they are not documented here.
