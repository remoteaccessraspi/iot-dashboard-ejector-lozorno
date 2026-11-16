# INVT Goodrive20-EU — manuály pre Cursor

Cieľové zariadenie v projekte `iot_dashboard`: **GD20-1R5G-S2-EU**, čerpadlo ejektorového chladiaceho zariadenia v Lozorne.

Zdroj: `docs/GD20-EU VFD Manual _V1.9.pdf`, najmä kapitoly 5 a 7. Čísla strán v súboroch tohto adresára sú strany PDF súboru. Skutočné nastavenia meniča treba pred zásahom prečítať.

## Súbory
- `MODBUS_REGISTERS.md`: overené adresy a škálovanie
- `PID_CONTROL.md`: interný PID a tlakový setpoint
- `CONFIGURATION.md`: RTU a prevádzkové parametre
- `VARIABLES.md`: názvoslovie aplikácie
- `TESTING.md`: bezpečný read-only test
- `CURSOR_INSTRUCTIONS.md`: pravidlá pre Cursor

**Zásada:** neprepisovať nastavenia ani neštartovať motor bez výslovného súhlasu a overenia bezpečnosti.
