# Modbus registre CK-8082E

Zdroj: výrobca Vr1.0, strana 8 (tabuľka); strana 9 (RTU príklad).

## Čítanie
- Funkcia: **FC03 — Read Holding Registers**.
- Register adresy sú **0-based PDU adresy**; PLC referencie 4xxxx sú iba alternatívny zápis.
- Odporúčané blokové čítanie: `address=0x0060`, `count=8`.

| Kanál | PDU hex | PDU decimal | PLC referencia | Význam |
|---|---|---:|---:|---|
| AI0 | 0x0060 | 96 | 40097 | analógový vstup 0 |
| AI1 | 0x0061 | 97 | 40098 | analógový vstup 1 |
| AI2 | 0x0062 | 98 | 40099 | analógový vstup 2 |
| AI3 | 0x0063 | 99 | 40100 | analógový vstup 3 |
| AI4 | 0x0064 | 100 | 40101 | analógový vstup 4 |
| AI5 | 0x0065 | 101 | 40102 | analógový vstup 5 |
| AI6 | 0x0066 | 102 | 40103 | analógový vstup 6 |
| AI7 | 0x0067 | 103 | 40104 | analógový vstup 7 |

## Dekódovanie
Každý register je 16-bitové celé číslo so znamienkom (two's complement). `physical_signal = signed_int16 / 1000`. Jednotka mA alebo V závisí od vyhotovenia.

```python
def decode_ck8082e(raw_u16: int) -> float:
    if not 0 <= raw_u16 <= 0xFFFF:
        raise ValueError('Register mimo uint16')
    signed = raw_u16 - 65536 if raw_u16 >= 32768 else raw_u16
    return signed / 1000.0
```

Príklady výrobcu: `16781 → 16.781 mA`; `5089 → 5.089 V`; `0xF6D7 → -2.345 V`.

**Pozor:** 24-bit ADC ≠ 24-bit Modbus hodnota. Nečítať dvojice registrov ako 32-bitové čísla. Nevykonávať zápisy do nedokumentovaných adries.
