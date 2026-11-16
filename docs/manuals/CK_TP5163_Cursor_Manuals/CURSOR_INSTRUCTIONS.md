# Cursor — implementačné pravidlá pre CK-TP5163

**Úloha:** V existujúcom projekte Raspberry Pi vytváraj/udržuj Modbus TCP driver pre CK-TP5163. Za autoritatívny zdroj registrov považuj `MODBUS_REGISTERS.md`, fyzické zapojenie `WIRING_AND_SAFETY.md`.

## Záväzné pravidlá
1. Nikdy nezamieňaj CK-TP5163 (16 DI/12 relé) za CK-TP5162 (16 DI/16 tranzistorových DO).
2. Používaj nulové Modbus offsety; nezvyšuj adresy o 1.
3. DI0–DI15 čítaj FC02, DO0–DO11 čítaj FC01, jednotlivý DO zapisuj FC05.
4. Pre bežné ovládanie nepoužívaj FC06 na bitové pole `0x0020`, ak môžeš použiť FC05; inak riskuješ prepísanie ostatných DO.
5. Zápis povoľ len do DO0–DO11 a do konfiguračných registrov výslovne uvedených v manuáli.
6. Zmenu timeoutu `0x0528` a uloženie cez `0x051F` vykonaj iba po explicitnom schválení; nepredpokladaj, že timeout znamená všetky relé OFF.
7. Najprv preskúmaj existujúcu architektúru projektu (Modbus klient, 5 s polling, MariaDB, API/HMI), potom navrhni minimálne zásahy.
8. Pred zmenou vytvor testy s mock Modbus serverom; neaktivuj relé pri testoch automaticky.
9. Po každom zápise urob readback a porovnaj skutočný stav; pri chybe loguj a označ stav ako neznámy.
10. IP, Unit ID, názvy kanálov a účel relé musia byť konfigurovateľné. IP default nie je automaticky IP produkčného zariadenia.
11. Použi verziu API knižnice `pymodbus` nainštalovanú v projekte; signatúru `slave`/`device_id` a návratové typy over podľa tejto verzie.
12. Žiadne nezdokumentované registre, bezpečnostné garancie alebo zapojenia nevymýšľaj; neistotu označ a vyžiadaj potvrdenie.

## Akceptačné testy
- FC02 offset 0 count 16 mapuje presne DI0–DI15.
- FC01 offset 0 count 12 mapuje presne DO0–DO11.
- FC05 offset 11 zapisuje DO11; offset 12 je odmietnutý.
- Hodnota `0x0528 = 50` sa zobrazuje ako 5.0 s.
- Odpojenie siete nevyvolá falošné stavy OFF/ON; HMI ukáže nedostupnosť.
- Pri pokuse o hromadný zápis sa vyžaduje explicitné potvrdenie a overenie masky.
- Zápisy sú auditované (čas, zariadenie, kanál, požadovaná a potvrdená hodnota, výsledok).

## Typická požiadavka pre Cursor
> Prečítaj všetky manuály v adresári CK_TP5163_Cursor_Manuals. Preskúmaj existujúci Modbus driver v projekte. Priprav implementačný plán pre CK-TP5163 s 16 DI a 12 reléovými DO, bez zásahov do živého hardvéru. Po schválení implementuj driver, testy a HMI mapovanie podľa týchto manuálov.
