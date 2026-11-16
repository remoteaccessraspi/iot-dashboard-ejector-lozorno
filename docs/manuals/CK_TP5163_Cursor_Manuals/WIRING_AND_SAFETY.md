# CK-TP5163 — svorky a bezpečnosť

Zdroj: výrobca Vr1.1, s. 4–6 a 9.

## Napájanie
- Napájací konektor: pin 1 = +24 V, pin 2 = 0 V, pin 3 = PE (s. 5).
- Povolené napájanie 10–30 V DC; nominálne 12/24 V DC.

## Digitálne vstupy
| Kanály | Svorky signálu | Spoločné svorky |
|---|---|---|
| DI0–DI7 | 1–8 | 9 a 10 (vnútorne spojené) |
| DI8–DI15 | 11–18 | 19 a 20 (vnútorne spojené) |

- Každá skupina 8 vstupov má vlastný COM; oba COM môžu mať rôzne potenciály.
- NPN: COM na +12/24 V; PNP: COM na 0 V; podporované aj bezpotenciálové kontakty (s. 4).
- Zapínacie napätie 8–30 V vzhľadom na COM; maximálne oneskorenie vstupu 2 ms (s. 9).

## Reléové výstupy
| Výstup | Svorka | Spoločná svorka |
|---|---:|---:|
| DO0 | 21 | 23 |
| DO1 | 22 | 23 |
| DO2 | 24 | 26 |
| DO3 | 25 | 26 |
| DO4 | 27 | 29 |
| DO5 | 28 | 29 |
| DO6 | 31 | 33 |
| DO7 | 32 | 33 |
| DO8 | 34 | 36 |
| DO9 | 35 | 36 |
| DO10 | 37 | 39 |
| DO11 | 38 | 39 |

- `30` a `40` = NC v zmysle **nepripojená / nepoužitá svorka** podľa tabuľky výrobcu; nie „normally closed“ reléový kontakt.
- Spoločné svorky sú zdieľané vždy pre dvojicu výstupov (DO0/1, DO2/3 atď.).
- Maximálne spínané napätie **30 V DC**; maximálny prúd **3 A odporová**, **2 A indukčná** záťaž (s. 4, 9).
- Nepoužívaj relé na priame spínanie 230 V AC: výrobca takú prevádzku v tejto verzii manuálu nepovoľuje.
- Pri indukčných záťažiach navrhni vhodnú ochranu a istenie; pred uvedením do prevádzky over elektrické zapojenie.
- IP20, pracovná teplota −35 až +75 °C; montáž na DIN35.
