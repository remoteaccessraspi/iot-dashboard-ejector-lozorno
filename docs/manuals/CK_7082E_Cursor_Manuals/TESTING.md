# CK-7082E — bezpečný test čítania

Zdroj: Vr1.1, str. 8–9.

1. Over model na štítku a typ vstupov (mA/V), skontroluj zapojenie podľa str. 6/12.
2. Zisti reálnu IP/RS485 konfiguráciu. Nehádaj IP adresu.
3. V režime **read-only** čítaj FC03, offset 96, count 8.
4. Skontroluj dĺžku odpovede, Modbus exception a hodnoty raw.
5. Preveď každé 16-bit slovo na signed int16 a vydel 1000.
6. Porovnaj aspoň dva kanály so známym referenčným signálom v správnych jednotkách.
7. Otestuj odpojenie komunikácie: označ hodnoty ako stale/invalid, nepublikuj ich ako čerstvé.
8. Až potom zapoj do 5-sekundového ticku existujúceho systému.

## Príklad pymodbus (API over podľa nainštalovanej verzie)
```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('REPLACE_WITH_VERIFIED_IP', port=502, timeout=2)
try:
    if not client.connect():
        raise ConnectionError('Modbus TCP unavailable')
    # pymodbus 3.x môže používať device_id=1 namiesto slave=1.
    response = client.read_holding_registers(address=96, count=8, slave=1)
    if response.isError():
        raise RuntimeError(f'Modbus error: {response}')
    values = [((v - 65536) if v >= 32768 else v) / 1000 for v in response.registers]
    print(values)
finally:
    client.close()
```
Pred použitím prispôsob volanie presnej verzii `pymodbus` v projekte; ukážka neobsahuje automatické opakovanie ani ukladanie do DB.
