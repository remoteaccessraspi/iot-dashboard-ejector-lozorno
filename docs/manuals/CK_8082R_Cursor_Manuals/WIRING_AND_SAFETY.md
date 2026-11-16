# Svorky, zapojenie a bezpečnosť
Zdroj: Vr1.0, str. 6–7 a 12.

| Svorka | Význam |
|---:|---|
| 1–16 | `IN0-`, `IN0+`, ... `IN7-`, `IN7+` (striedavo mínus/plus) |
| 17 | VIN +10 až +30 V DC |
| 18 | GND napájania |
| 19 | RS485 B (negatívna vetva podľa výrobcu) |
| 20 | RS485 A (pozitívna vetva podľa výrobcu) |
| 21–22 | NC — nezapájať |

Každý analógový vstup je **diferenciálny**. Pri prúdovom meraní musí byť konkrétny modul objednaný/kalibrovaný s interným presným meracím rezistorom (str. 6). Samotná deklarácia ±20 mA neznamená, že ľubovoľný kus je univerzálne prepínateľný medzi mA a V.

RS485 používa zbernicovú topológiu, nie hviezdu ani kruh; krátke odbočky, správne zakončenie podľa fyzickej siete. Pred pripojením preveriť polaritu A/B podľa označenia adaptéra, ktoré sa môže líšiť. Nepripájať napätie mimo overeného rozsahu konkrétneho kusu. Izolačné napätie podľa výrobcu 2500 V DC; neznamená dovolené trvalé prevádzkové napätie na vstupe.
