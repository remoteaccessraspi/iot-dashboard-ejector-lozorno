# Pokyny pre Cursor — integrácia CK-8082E

## Záväzné pravidlá
1. Najprv prečítať všetky súbory v tomto adresári a preskúmať existujúci Modbus driver, konfiguráciu, databázu a HMI projektu `iot_dashboard`.
2. Nezamieňať **CK-8082E** (Ethernet + RS485) s **CK-8082R** (RS485) alebo **CK-7082E** (16-bit ADC).
3. Implementovať iba zdokumentované **read-only FC03** čítanie adries 96–103.
4. Každú hodnotu dekódovať ako signed int16 a deliť 1000. 24-bitové rozlíšenie ADC neznamená 24-bitový Modbus formát.
5. Nepredpokladať predvolenú IP, TCP Unit ID, kalibráciu mA/V ani zapisovateľné registre.
6. Zariadenie musí mať konfigurovateľný transport TCP/RTU, parametre komunikácie, názvy kanálov, jednotky a škálovanie.
7. Pracovať v existujúcom 5-sekundovom cykle, bez blokovania ostatných Modbus zariadení; opätovné spojenie a timeout musia byť robustné.
8. Uchovávať raw hodnotu, dekódovaný signál, fyzikálnu hodnotu, timestamp a quality flag; nepovažovať staré meranie za čerstvé.
9. Najprv navrhnúť zmeny, vytvoriť unit testy, až potom implementovať. Žiadne zápisy do hardvéru bez schválenia.

## Príklad zadania
> Prečítaj `docs/CK_8082E/*.md`, skontroluj architektúru projektu a navrhni read-only integráciu CK-8082E do existujúceho Modbus polling systému. Zachovaj súčasnú DB a HMI architektúru, pridaj konfiguráciu kanálov a testy signed-int16. Nevykonávaj zápis do modulu.
