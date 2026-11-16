# Komunikácia a konfigurácia

Zdroj: INVT V1.9, `docs/GD20-EU VFD Manual _V1.9.pdf`. Skupina P14 je na stranách 100–102, P00.01 na strane 37, P05.04 a P05.10 na stranách 62 a 64, P01.21 na strane 50. Čísla strán sú strany PDF súboru.

| Parameter | Adresa | PDF |
|---|---|---|
| `P14.00` | `0x0E00` | slave adresa 1–247, továrensky 1 |
| `P14.01` | `0x0E01` | `3` = 9600, `4` = 19200 a je továrenská hodnota |
| `P14.02` | `0x0E02` | `0` = 8N1 RTU, `1` = 8E1 RTU a je továrenská hodnota, `2` = 8O1, `3` = 8N2 |
| `P14.04` | `0x0E04` | timeout 0,0–60,0 s, 0,0 = vypnutý |
| `P00.01` | `0x0001` | `2` = príkaz z komunikácie |

YAML žiada `P14.01 = 3` a `P14.02 = 0`, teda 9600 8N1. Master tieto dva parametre nezapisuje. Slave v YAML je 100.

Pri štarte master zapíše len tieto štyri, a len keď sa líšia od meniča:

| Parameter | Adresa | Zapíše | Podmienka |
|---|---|---|---|
| `P01.21` | `0x0115` | 0, bez automatického reštartu po výpadku | hneď |
| `P05.10` | `0x050A` | 8, bit3 obracia S4 | hneď |
| `P00.01` | `0x0001` | 2, príkaz z komunikácie | len keď menič stojí |
| `P05.04` | `0x0504` | 6, S4 = voľný dobeh | len keď menič stojí |

S4 je v kľude zopnutý. Obrátená logika z rozopnutia, aj z prerušeného vodiča, urobí voľný dobeh. Program stav S4 číta z `0x300A` bit3.

Menič podľa tohto PDF používa Modbus RTU cez RS485, nie Modbus TCP.

Niektoré parametre menič odmietne zapísať za chodu. PDF to hovorí v kapitole 7.4.1. Preto program P00.01 a P05.04 pri bežiacom motore odloží na prvé státie.
