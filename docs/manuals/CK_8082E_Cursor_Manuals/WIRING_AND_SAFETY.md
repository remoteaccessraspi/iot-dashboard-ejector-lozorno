# Zapojenie a bezpečnosť

Zdroj: strany 6 a 12 výrobného manuálu.

## Svorky
| Číslo | Označenie | Význam |
|---:|---|---|
| 1–16 | IN0−, IN0+, ... IN7−, IN7+ | 8 diferenciálnych vstupov, každý pár mínus/plus |
| 17 | VIN | +10 až +30 V DC |
| 18 | GND | napájacia zem |
| 19 | B | RS485− |
| 20 | A | RS485+ |
| 21–22 | NC | nezapájať |
| 2× RJ45 | ETH | Ethernet / kaskáda |

Pre kanál `n` platí svorka mínus `2*n+1`, plus `2*n+2` (n=0..7).

## Kritické pravidlá
- Diferenciálne meranie: signál priviesť medzi INn+ a INn−, nie automaticky proti GND.
- **Prúdový vstup vyžaduje variant s interným presným meracím rezistorom, osadeným a kalibrovaným výrobcom pri objednávke** (str. 6). Samotná softvérová voľba mA nestačí.
- Neprekračovať dovolené vstupné limity; rozsah závisí od variantu. Napájanie pripájať pri vypnutom zdroji.
- Pre Ethernet používať štandardnú priemyselnú sieť; nepredpokladať, že kaskáda poskytuje redundanciu.
- V manuáli uvedená izolácia 2500 V DC nie je povolenie na pripojenie sieťového napätia k analógovým vstupom.
