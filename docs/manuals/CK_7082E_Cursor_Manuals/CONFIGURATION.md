# CK-7082E — konfigurácia komunikácie

Zdroj: Vr1.1, str. 6–9.

## Modbus RTU
- RS485: svorka 19 `B` (negatívna), svorka 20 `A` (pozitívna).
- Predvolené: **9600 baud, 8N1, slave adresa 1** (str. 8).
- Adresy slave: 1–247; podporované rýchlosti 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200 bps.
- Manuál spomína zmenu adresy/rýchlosti príkazmi, ale neobsahuje konkrétne zapisovacie registre/príkazy. Bez dokumentácie výrobcu ich nevymýšľaj.

## Modbus TCP
- Dva ethernetové porty s kaskádovaním (str. 7), štandardný Modbus TCP.
- **Predvolená IP adresa, port a postup zmeny IP nie sú v tomto PDF uvedené.** Port 502 je bežný štandard Modbus TCP, nie explicitne potvrdený údaj tohto manuálu.
- Pred pripojením over IP adresu na fyzickom zariadení alebo v dokumentácii výrobcu; nepovažuj `192.168.1.30` za overený údaj CK-7082E.
- Unit ID 1 je použité v ukážke Modbus TCP (str. 9); podľa konkrétnej konfigurácie over na zariadení.

## Príklad YAML (návrh)
```yaml
ck7082e:
  enabled: false
  protocol: tcp
  host: null  # vyplniť po overení
  port: 502   # štandardný predpoklad, overiť
  unit_id: 1
  start_address: 96
  channel_count: 8
  poll_interval_s: 5
  input_unit: mA  # iba ak je potvrdený prúdový variant
```
Konfiguračný príklad nie je príkaz na zmenu nastavení samotného modulu.
