-- ============================================
-- IoT Dashboard - MariaDB initialization
-- ============================================
-- Do NOT use this file for table definitions.
-- Canonical schema:
--
--   sudo mysql -e "CREATE DATABASE IF NOT EXISTS ejector CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
--   sudo mysql ejector < /home/pi/iot-dashboard-ejector-lozorno/db/schema_v1.0.0.sql
--   sudo mysql ejector < /home/pi/iot-dashboard-ejector-lozorno/db/migrate_invt_gd20.sql
--   sudo mysql ejector < /home/pi/iot-dashboard-ejector-lozorno/db/migrate_em2rs_556.sql
--   sudo mysql ejector < /home/pi/iot-dashboard-ejector-lozorno/db/migrate_alarms.sql
--
-- The same order is in scripts/mariadb-hot-schema.sh. Archive sync fails if
-- a table is missing on the SD instance.
--
-- (Older 4-channel init.sql was removed — it did not match the app.)
-- ============================================

CREATE DATABASE IF NOT EXISTS ejector
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
