# CK-TP5163 — premenné pre Python, DB a HMI

## Kanály
- `di_0` až `di_15`: `bool`, **read-only**, získané cez FC02 (offset 0–15).
- `do_0` až `do_11`: `bool`, readback cez FC01, požadovaná hodnota cez FC05 (offset 0–11).
- `di_mask`: `uint16`, read-only, FC03 adresa 34; bit `i` zodpovedá `di_i`.
- `do_mask`: `uint16`, FC03/06 adresa 32; platné len bity 0–11 (`0x0FFF`).
- `communication_timeout_ds`: `uint16`, FC03/06 adresa 1320, jednotka 0,1 s; `0` deaktivuje timeout.
- `settings_save_command`: zápis `0x5A51` cez FC06 na adresu 1311; **nie bežná meraná premenná**.

## Odporúčaná aplikačná schéma (nie register map výrobcu)
```yaml
device:
  model: CK-TP5163
  host: 192.168.1.30  # len továrenský default; prepisuje sa podľa inštalácie
  port: 502
  unit_id: 1          # z príkladu výrobcu; overiť na konkrétnom kuse
  poll_interval_s: 5 # projektové nastavenie Raspberry Pi, nie vlastnosť modulu
channels:
  di_count: 16
  do_count: 12
  di_names: [di_0, di_1, di_2, di_3, di_4, di_5, di_6, di_7, di_8, di_9, di_10, di_11, di_12, di_13, di_14, di_15]
  do_names: [do_0, do_1, do_2, do_3, do_4, do_5, do_6, do_7, do_8, do_9, do_10, do_11]
```

## Pravidlá pre pomenovanie
- Fyzický kanál je nulovo indexovaný: `DO0` = `do_0` = coil offset 0.
- Logický názov (napr. `pump_enable`) je **mapovanie projektu**, nie vlastnosť hardvéru; vyžaduje explicitnú konfiguráciu.
- Oddeľ `requested_do_i` (príkaz) od `actual_do_i` (potvrdený stav čítaním).
- Pri zlyhaní komunikácie označ hodnotu ako `stale`/`unknown`; nepovažuj poslednú známu hodnotu za aktuálnu.
- Pred zápisom validuj index `0..11`, hodnotu `bool` a oprávnenie operátora.
