# Interný PID regulátor čerpadla

Zdroj: INVT Goodrive20-EU V1.9, `docs/GD20-EU VFD Manual _V1.9.pdf`. Skupina P09 je na stranách 88–89, P00.06 a poznámka k AI2 na strane 40. Čísla strán sú strany PDF súboru.

| Parameter | Funkcia | Hodnota v PDF | Čo s tým robí program |
|---|---|---|---|
| `P00.01` | zdroj RUN/STOP | `2` = komunikácia | pri štarte zapíše 2, keď menič stojí |
| `P00.06` | zdroj frekvencie A | `7` = procesný PID | nečíta ani nezapisuje |
| `P00.07` | zdroj frekvencie B | PID beží aj keď je tu `7` | nečíta ani nezapisuje |
| `P09.00` | zdroj PID referencie | `6` = Modbus `0x2002` | nezapisuje |
| `P09.02` | zdroj spätnej väzby | `1` = AI2 | nezapisuje |
| `P09.03` | smer PID | `0` kladný, `1` záporný | nezapisuje |

Interný PID sa aktivuje len na meniči: P00.06 = 7, alebo P00.07 = 7. Master oba parametre pri behu nečíta a do meniča ich nezapisuje. Sedmička pri P00.06 v YAML je len očakávaná hodnota pre diagnostický skript, nie nastavenie, ktoré by program posielal.

PID referencia v meniči je relatívna: 100 % zodpovedá 100 % signálu spätnej väzby. Register `0x2002` má rozsah 0–1000 = 0–100,0 %.

Program berie žiadanú hodnotu `gd20_setpoint_kpa` a zapíše ju na `0x2002`. Prevod je lineárny podľa YAML: 0–1500 kPa → 0–1000. Mimo tohto rozsahu zápis neurobí.

Spätnú väzbu program na `0x2003` nezapisuje. Menič ju má brať z vlastného AI2 (`P09.02 = 1`). AI2 číta program z `0x300D` ako 0,00–10,00 V. Podľa PDF zodpovedá 20 mA napätiu 10 V. Na kPa to prepočíta YAML: 0–10 V ako 0–20 mA a potom 4–20 mA ako 0–1500 kPa. Výsledok je v DB `ai2_kpa`, alias `p_gen_prim_from_frq`.

Čítaná PID referencia `0x3008` a spätná väzba `0x3009` sú percentá. Program ich ukladá ako `pid_setpoint_kpa` a `pid_feedback_kpa` po prevode 0–100 % → 0–1500 kPa.
