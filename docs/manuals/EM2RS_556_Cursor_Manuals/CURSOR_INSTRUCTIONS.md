# Záväzné pravidlá pre Cursor

Zdroj: Leadshine EM2RS Series Modbus RS485 Stepper Drive User Manual V1.5 (2021-08-30), https://www.leadshine.com/upfiles/downloads/04bbeba0c8c1196dc41e7d54c811d7d9_1650879175499.pdf

1. Najprv preskúmaj existujúcu implementáciu `iot_dashboard` a existujúce Modbus RTU polling/locking.
2. Použi dokumentáciu ako zdroj; pri nejasnej adrese si vyžiadaj presnú stranu PDF a neimprovizuj.
3. Predvolene iba FC03 čítanie. Žiadny FC06/FC16 bez explicitného povolenia používateľa.
4. Nevykonávaj reset parametrov, EEPROM save, forced enable, homing ani JOG automaticky.
5. Rozlišuj mechanické kroky ETS 12C a interné jednotky Pulse/revolution drivera.
6. Nepovažuj softvérovú polohu za nezávislé meranie polohy.
7. Chybné/oneskorené dáta označ ako neplatné; nezapisuj falošné nuly do DB.
8. Pred zmenou implementácie ukáž zoznam upravených súborov a plán testov.
9. Zdieľanú RS485 zbernicu neotváraj paralelne viacerými klientmi.
10. Zachovaj existujúci 5-sekundový tick a neblokuj ho dlhým homingom.
