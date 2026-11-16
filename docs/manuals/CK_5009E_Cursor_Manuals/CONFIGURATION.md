# CK-5009E — Komunikačná konfigurácia

## Ethernet / Modbus TCP
- Podpora Ethernet 10/100 Mbit a Modbus TCP podľa str. 3, 7–8.
- **Predvolená IP adresa CK-5009E nie je v manuáli spoľahlivo uvedená.** Obrázok na str. 7 zobrazuje *iný modul CK-3168E* s IP `192.168.1.30`; nepovažovať to za CK-5009E default.
- Port `502` je štandard Modbus TCP, ale tento konkrétny manuál ho výslovne neudáva. Overiť na zariadení.
- Manuál neuvádza konkrétny príkaz pre zmenu IP, masky, gateway ani reset siete. **Nevymýšľať registre ani konfiguračné API.**
- Obrázky CK-5009E ukazujú jeden konektor ETH a jeden RS485 (str. 6, 12). Názov súboru „Ethernet Cascade“ nepreukazuje dva Ethernet porty tohto modelu.

## RS485 / Modbus RTU
- Predvolené: slave adresa 1, `9600`, 8N1 (str. 8).
- Povolené slave adresy 1–247; podporované baud: 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200 (str. 8).
- Nastavenie adresy/baud je podľa výrobcu možné príkazmi, ale ich konkrétne rámce v PDF chýbajú. Nemení sa automaticky.
- RS485 A = svorka 20, B = svorka 19 (str. 6).

## Integrácia Raspberry Pi
- TCP: konfigurovateľná IP, port, unit ID, timeout, retry; jeden poller, 5 s cyklus.
- RTU: zdieľaný RS485 bus; nevytvárať paralelné nekontrolované master spojenia.
- Komunikačné chyby nesmú spôsobiť automatický zápis alebo preklopenie výstupov.
