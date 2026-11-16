# Premenné a škálovanie
Zdroj pre register/prevod: Vr1.0, str. 8–9. Názvy sú návrh pre projekt, nie názvy výrobcu.

| Premenná | Kanál | Register | Jednotka |
|---|---:|---:|---|
| `ck8082r_ai0` | 0 | 96 | mA alebo V |
| `ck8082r_ai1` | 1 | 97 | mA alebo V |
| `ck8082r_ai2` | 2 | 98 | mA alebo V |
| `ck8082r_ai3` | 3 | 99 | mA alebo V |
| `ck8082r_ai4` | 4 | 100 | mA alebo V |
| `ck8082r_ai5` | 5 | 101 | mA alebo V |
| `ck8082r_ai6` | 6 | 102 | mA alebo V |
| `ck8082r_ai7` | 7 | 103 | mA alebo V |

```python
def decode_ck8082r(raw: int) -> float:
    if not 0 <= raw <= 0xFFFF:
        raise ValueError('raw must be uint16')
    signed = raw - 65536 if raw >= 32768 else raw
    return signed / 1000.0
```

Príklady: `16781 -> 16.781 mA`, `5089 -> 5.089 V`, `0xF6D7 -> -2.345 V`.

Pre každý kanál evidovať `raw`, `value`, `unit`, `range`, `timestamp`, `quality` (`good`, `timeout`, `modbus_error`, `unconfigured`). Konkrétny typ signálu a fyzikálne škálovanie tlaku/teploty/prietoku definovať **osobitne pre každý kanál** podľa senzora a výrobnej varianty modulu. Pre 4–20 mA napr. `engineering = low + (mA-4)*(high-low)/16`; ide o projektové škálovanie, nie register modulu. Nezamieňať chybu komunikácie s nulovou hodnotou.
