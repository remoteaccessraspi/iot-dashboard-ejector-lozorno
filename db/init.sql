-- ============================================
-- IoT Dashboard - MariaDB initialization
-- ============================================
-- Do NOT use this file for table definitions.
-- Canonical schema:
--
--   sudo mysql -e "CREATE DATABASE IF NOT EXISTS ejector CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
--   sudo mysql ejector < /home/pi/iot-dashboard-ejector-lozorno/db/schema_v1.0.0.sql
--
-- (Older 4-channel init.sql was removed — it did not match the app.)
-- ============================================

CREATE DATABASE IF NOT EXISTS ejector
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
