# Testovací postup CK-8082E

## 1. Pred pripojením
- Potvrdiť typ signálu (prúdový / napäťový variant), zapojenie, napájanie a konkrétne sieťové parametre.
- Vybrať TCP alebo RTU, nehádať IP adresu.

## 2. Read-only komunikácia
- `FC03`, `address=96`, `count=8`.
- Skontrolovať presne osem 16-bitových hodnôt.
- Pre každý kanál dekódovať signed int16 a vydeliť 1000.

## 3. Referenčné testy dekódovania (bez hardvéru)
```python
from math import isclose

def decode(raw):
    return (raw - 65536 if raw >= 32768 else raw) / 1000

assert isclose(decode(16781), 16.781)
assert isclose(decode(5089), 5.089)
assert isclose(decode(0xF6D7), -2.345)
assert isclose(decode(0), 0)
```

## 4. Test s referenčným signálom
Na vhodne kalibrovaný vstup priviesť známy signál, overiť jednotku, polaritu, správny kanál a stabilitu merania. Neaplikovať mA na neoverený napäťový variant.

## 5. Integrácia
Testovať timeout, odpojenie, obnovenie spojenia, chybné dáta, chýbajúcu konfiguráciu. Pri výpadku nevydávať poslednú známu hodnotu za aktuálnu; DB/HMI musí mať kvalitu a timestamp.
