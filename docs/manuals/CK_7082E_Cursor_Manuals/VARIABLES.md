# CK-7082E — premenné a škálovanie

Zdroj: Vr1.1, str. 3, 8–9. Názvy premenných nižšie sú **návrh pre aplikáciu**, nie názvy od výrobcu.

| Názov | Kanál | Offset | Typ raw | Engineering value |
|---|---:|---:|---|---|
| `ck7082e_ai0_raw`, `ck7082e_ai0_value` | 0 | 96 | int16 | raw / 1000, jednotka podľa variantu |
| `ck7082e_ai1_raw`, `ck7082e_ai1_value` | 1 | 97 | int16 | raw / 1000, jednotka podľa variantu |
| `ck7082e_ai2_raw`, `ck7082e_ai2_value` | 2 | 98 | int16 | raw / 1000, jednotka podľa variantu |
| `ck7082e_ai3_raw`, `ck7082e_ai3_value` | 3 | 99 | int16 | raw / 1000, jednotka podľa variantu |
| `ck7082e_ai4_raw`, `ck7082e_ai4_value` | 4 | 100 | int16 | raw / 1000, jednotka podľa variantu |
| `ck7082e_ai5_raw`, `ck7082e_ai5_value` | 5 | 101 | int16 | raw / 1000, jednotka podľa variantu |
| `ck7082e_ai6_raw`, `ck7082e_ai6_value` | 6 | 102 | int16 | raw / 1000, jednotka podľa variantu |
| `ck7082e_ai7_raw`, `ck7082e_ai7_value` | 7 | 103 | int16 | raw / 1000, jednotka podľa variantu |


## Konverzia
```python
def to_signed16(word: int) -> int:
    word &= 0xFFFF
    return word - 65536 if word >= 32768 else word

def decode_input(word: int) -> float:
    return to_signed16(word) / 1000.0
```

Pri prúdovom variante výsledok interpretuj v mA, pri napäťovom vo V. Neodvodzuj typ vstupu iba z čísla registra.

## Príklad škálovania snímača tlaku
Pre overený snímač 4–20 mA a rozsah 0–1000 kPa:
```python
def current_to_kpa(current_ma: float) -> float:
    return (current_ma - 4.0) / 16.0 * 1000.0
```
Toto je **ilustračná aplikačná konverzia**, nie vlastnosť CK-7082E. Rozsah a jednotky nastav podľa konkrétneho snímača. Pri výpadku Modbus alebo mimo rozsahu nepovažuj poslednú hodnotu za aktuálne meranie; ulož aj stav kvality a čas posledného úspešného čítania.
