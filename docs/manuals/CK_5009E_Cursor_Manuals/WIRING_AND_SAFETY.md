# CK-5009E — Zapojenie a bezpečnosť

Zdroj: Vr1.0, str. 5–6 a 12. Modul má **NPN MOSFET low-side výstupy**, nie galvanicky oddelené suché kontakty.

| Svorka | Signál | Funkcia |
|---:|---|---|
| 1 | DO0 | spínaný záporný pól záťaže 0 |
| 2 | DO+ | kladný pól záťaže 0 |
| 3 | DO1 | spínaný záporný pól záťaže 1 |
| 4 | DO+ | kladný pól záťaže 1 |
| 5 | DO2 | spínaný záporný pól záťaže 2 |
| 6 | DO+ | kladný pól záťaže 2 |
| 7 | DO3 | spínaný záporný pól záťaže 3 |
| 8 | DO+ | kladný pól záťaže 3 |
| 9 | DO4 | spínaný záporný pól záťaže 4 |
| 10 | DO+ | kladný pól záťaže 4 |
| 11 | DO5 | spínaný záporný pól záťaže 5 |
| 12 | DO+ | kladný pól záťaže 5 |
| 13 | DO6 | spínaný záporný pól záťaže 6 |
| 14 | DO+ | kladný pól záťaže 6 |
| 15 | DO7 | spínaný záporný pól záťaže 7 |
| 16 | DO+ | kladný pól záťaže 7 |
| 17 | VIN | napájanie +9 až +30 V DC |
| 18 | GND | napájacia zem |
| 19 | B | RS485 B |
| 20 | A | RS485 A |
| 21–22 | NC | nezapojené |

**Pred pripojením:** overiť napätie a prúd záťaže, spoločné referenčné potenciály, ochranu proti indukčným špičkám, poistky a polaritu. Výrobca uvádza 1,25 A, ale nie detailné tepelné derating podmienky. Pri cievkach zabezpečiť primeranú ochranu podľa typu záťaže.

Výrobca na str. 5 kreslí ekvivalent NPN spínača proti COM. Str. 6 a 12 zobrazujú svorky DO+/DOx. Presné interné prepojenie DO+ s VIN alebo spoločnou zemou nie je dostatočne rozkreslené — pred zapojením merať/overiť u výrobcu. Nikdy nepripájať sieťových 230 V priamo na DO.

PDF neuvádza garantovaný bezpečný stav pri strate Modbus spojenia. Nenavrhovat watchdog ani fail-safe logiku ako existujúcu funkciu zariadenia.
