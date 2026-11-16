# CK-5009E — Premenné a API

## Logické premenné

| Názov | Typ | Zdroj | Význam |
|---|---|---|---|
| `ck5009e.do0` … `ck5009e.do7` | bool | coils 0–7, FC01 | potvrdený logický stav výstupu |
| `ck5009e.do0_command` … `ck5009e.do7_command` | bool | aplikácia | požadovaný stav; nie je dôkaz vykonania |
| `ck5009e.connected` | bool | komunikačná vrstva | úspešná komunikácia v určenom intervale |
| `ck5009e.last_success_utc` | datetime/null | aplikácia | posledné úspešné čítanie |
| `ck5009e.error` | string/null | aplikácia | posledná chyba komunikácie |

`doN = true` znamená podľa výrobcu zapnutú záťaž, MOSFET zopnutý na COM/GND; neznamená potvrdený prúd záťažou (str. 8–9).

## Konfigurácia (príklad, nie továrenské hodnoty)
```yaml
ck5009e:
  enabled: false
  transport: tcp
  host: null          # vyplniť podľa skutočného zariadenia
  port: 502           # štandardný Modbus TCP port, v PDF nie je explicitne potvrdený
  unit_id: 1          # RTU default; pre TCP overiť podľa zariadenia
  poll_interval_s: 5
  timeout_s: 1.0
  writes_enabled: false
  outputs:
    - {channel: 0, name: do0}
    - {channel: 1, name: do1}
    - {channel: 2, name: do2}
    - {channel: 3, name: do3}
    - {channel: 4, name: do4}
    - {channel: 5, name: do5}
    - {channel: 6, name: do6}
    - {channel: 7, name: do7}
```

Mená technologických veličín (`pump_enable`, `alarm`, ...) sa priradia až podľa fyzického zapojenia. Neodvodzovať ich z manuálu.
