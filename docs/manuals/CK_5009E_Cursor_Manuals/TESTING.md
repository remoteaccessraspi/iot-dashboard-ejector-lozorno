# CK-5009E — Testovací protokol

## Fáza A: bez zápisov
1. Overiť štítok modelu a hardvérovú verziu, napájanie a výstupné svorky.
2. Identifikovať reálnu IP/port alebo RS485 slave adresu; nevychádzať z obrázku CK-3168E.
3. Otvoriť Modbus spojenie s timeoutom.
4. Prečítať `FC01`, adresa 0, počet 8. Výsledok uložiť ako `do0..do7`.
5. Opakovať po 5 s; zaznamenať timeouty a čas posledného úspechu.
6. Overiť, že žiadna chyba automaticky neaktivuje výstup.

## Fáza B: zápisy len so súhlasom
1. Fyzicky odpojiť nebezpečné záťaže, použiť bezpečnú testovaciu DC záťaž.
2. Vyžiadať explicitné schválenie konkrétneho kanála a stavu.
3. Zápis jedného kanála `FC05`; následne readback `FC01`.
4. Zápis všetkých 8 `FC0F` len pri testovaní a po schválení celej masky.
5. Overiť rozdiel medzi logickým readback a skutočným napätím/prúdom záťaže.
6. Vyskúšať reštart modulu a výpadok spojenia **len v bezpečnom laboratórnom režime**; výsledky zdokumentovať, nepredpokladať fail-safe.

## Referenčný príklad z PDF str. 9
Maska `0xC3` => ON: DO0, DO1, DO6, DO7; OFF: DO2–DO5. Pri skúške s reálnym zariadením ide o **aktívny zásah**.
