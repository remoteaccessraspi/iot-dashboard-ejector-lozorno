# Pokyny pre Cursor — CK-8082R

## Úloha
Integrovať 8-kanálový modul Chengkong CK-8082R do existujúcej Raspberry Pi aplikácie (Modbus RTU, DB, HMI) bez zásahu do existujúcej regulácie. Najprv analyzuj projekt a aktuálny RS485 polling; navrhni minimálnu zmenu, až potom implementuj.

## Záväzné pravidlá
1. Jediným výrobcom potvrdeným Modbus čítaním v PDF je **FC03**, registre **96–103**, 8 × signed int16, `/1000`.
2. Nepoužívaj Modbus TCP ani 32-bitový dátový formát na merania; 24 bit označuje ADC.
3. Žiadne zápisy (FC06/FC16) bez ďalšieho výrobného manuálu s konkrétnymi registrami.
4. Port, slave ID, jednotku a merací rozsah nastaviteľné v konfigurácii; nepoužívať globálnu jednotku pre všetky kanály.
5. Nevyvodzuj, že každý kus podporuje prúdové meranie: výrobca uvádza potrebu interného odporu a továrenskej kalibrácie.
6. Na zbernici s viacerými slave modulmi zachovať jeden sériový polling worker a bezkolízny prístup k portu.
7. Časové pečiatky, kvalita dát, timeouty a diagnostika sú povinné. Pri chybe neposielať nulu ako platné meranie.
8. HMI aj databáza majú používať jednoznačné názvy `ck8082r_ai0` ... `ck8082r_ai7`; fyzikálne názvy senzorov konfigurovať zvlášť.
9. Zmena komunikácie alebo fyzického nastavenia modulu vyžaduje explicitné schválenie používateľa.
10. Ak existujúca aplikácia používa iné pomenovanie alebo schému DB, uprednostni jej konvencie a zdokumentuj mapovanie.

## Požadované výstupy
- Prehľad existujúcej architektúry a bodu integrácie
- Konfiguračný blok pre nový modul
- Čítací driver a unit testy prevodu int16
- Návrh mapovania DB a HMI bez rozbitia existujúcich zariadení
- Zoznam neoverených údajov vyžadujúcich fyzický test
