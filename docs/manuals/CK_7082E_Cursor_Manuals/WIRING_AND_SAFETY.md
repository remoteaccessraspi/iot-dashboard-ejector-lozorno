# CK-7082E — svorky, zapojenie a bezpečnosť

Zdroj: Vr1.1, schéma str. 6 a 12.

## Svorky
| Svorky | Význam |
|---|---|
| 1 / 2 | IN0- / IN0+ |
| 3 / 4 | IN1- / IN1+ |
| 5 / 6 | IN2- / IN2+ |
| 7 / 8 | IN3- / IN3+ |
| 9 / 10 | IN4- / IN4+ |
| 11 / 12 | IN5- / IN5+ |
| 13 / 14 | IN6- / IN6+ |
| 15 / 16 | IN7- / IN7+ |
| 17 / 18 | VIN (+10 až +30 V DC) / GND |
| 19 / 20 | RS485 B(-) / A(+) |
| 21 / 22 | NC / NC — nepripájať |

Každý kanál je diferenciálny. Dodrž polaritu `INn+` a `INn-` podľa schémy na str. 6/12.

**Prúdové meranie:** manuál na str. 6 výslovne požaduje objednať prúdový variant so vstavaným presným meracím odporom a kalibráciou. Nepripájaj prúdovú slučku k neoverenému napäťovému variantu.

- Použi vhodné istenie napájania a ochranu proti prepätiu podľa projektu.
- RS485 veď ako zbernicu, nie hviezdu/kruh; pri dlhých trasách rieš termináciu a krátke odbočky (str. 7).
- Výrobca uvádza izolačné skúšobné napätie 2500 V DC, nie povolenie priamo pripájať sieťové napätie na analógové vstupy.
- Pri montáži odpoj napájanie; pred oživením skontroluj typ signálu, polaritu a rozsah.
