-- Referenčný obraz schémy RAM inštancie po db/schema_v1.0.0.sql a db/migrate_*.sql.
-- Súbor maže a znova zakladá tabuľky. Nikdy ho nespúšťaj nad živou databázou.

/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19-11.8.6-MariaDB, for debian-linux-gnu (aarch64)
--
-- Host: localhost    Database: ejector
-- ------------------------------------------------------
-- Server version	11.8.6-MariaDB-0+deb13u1 from Debian

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;

--
-- Table structure for table `alarm_event`
--

DROP TABLE IF EXISTS `alarm_event`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `alarm_event` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `code` varchar(32) NOT NULL,
  `source` varchar(32) NOT NULL,
  `device_id` smallint(6) NOT NULL DEFAULT 0,
  `class` enum('ALARM','WARNING') NOT NULL,
  `message` varchar(255) NOT NULL,
  `details` text DEFAULT NULL,
  `inhibit_run` tinyint(4) NOT NULL DEFAULT 0,
  `release_policy` enum('NONE','ACK','ACK_AND_HOLD_RUN') NOT NULL DEFAULT 'NONE',
  `ack_ts` timestamp NULL DEFAULT NULL,
  `cleared_ts` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_open` (`code`,`source`,`device_id`,`cleared_ts`),
  KEY `idx_ts` (`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Alarm and warning occurrences';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `alarm_state`
--

DROP TABLE IF EXISTS `alarm_state`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `alarm_state` (
  `code` varchar(32) NOT NULL,
  `source` varchar(32) NOT NULL,
  `device_id` smallint(6) NOT NULL DEFAULT 0,
  `class` enum('ALARM','WARNING') NOT NULL,
  `message` varchar(255) NOT NULL,
  `details` text DEFAULT NULL,
  `condition_on` tinyint(4) NOT NULL DEFAULT 1,
  `latched` tinyint(4) NOT NULL DEFAULT 0,
  `inhibit_run` tinyint(4) NOT NULL DEFAULT 0,
  `release_policy` enum('NONE','ACK','ACK_AND_HOLD_RUN') NOT NULL DEFAULT 'NONE',
  `event_id` bigint(20) unsigned DEFAULT NULL,
  `raised_ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `ack_ts` timestamp NULL DEFAULT NULL,
  `ack_source` varchar(32) DEFAULT NULL,
  `cleared_ts` timestamp NULL DEFAULT NULL,
  `updated_ts` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`code`,`source`,`device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='One open alarm or warning';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `control`
--

DROP TABLE IF EXISTS `control`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `control` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `parameter` varchar(32) NOT NULL,
  `value` varchar(64) NOT NULL,
  `source` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ts` (`ts`),
  KEY `idx_param_ts` (`parameter`,`ts`),
  KEY `idx_parameter` (`parameter`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Control parameters written by HMI or system logic';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `control_state`
--

DROP TABLE IF EXISTS `control_state`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `control_state` (
  `parameter` varchar(32) NOT NULL,
  `value` varchar(64) NOT NULL,
  `source` varchar(32) DEFAULT NULL,
  `updated_ts` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`parameter`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `conversion_table`
--

DROP TABLE IF EXISTS `conversion_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `conversion_table` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `current_loop_id` bigint(20) unsigned DEFAULT NULL,
  `p1` float DEFAULT NULL,
  `p2` float DEFAULT NULL,
  `p3` float DEFAULT NULL,
  `p4` float DEFAULT NULL,
  `p5` float DEFAULT NULL,
  `p6` float DEFAULT NULL,
  `p7` float DEFAULT NULL,
  `p8` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_current_loop_id` (`current_loop_id`),
  KEY `idx_ts` (`ts`),
  KEY `idx_current_loop_id` (`current_loop_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Converted physical quantities calculated from current_loop';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `current_loop`
--

DROP TABLE IF EXISTS `current_loop`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `current_loop` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `i1` float DEFAULT NULL,
  `i2` float DEFAULT NULL,
  `i3` float DEFAULT NULL,
  `i4` float DEFAULT NULL,
  `i5` float DEFAULT NULL,
  `i6` float DEFAULT NULL,
  `i7` float DEFAULT NULL,
  `i8` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ts` (`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Raw current loop inputs (4–20 mA), stored in mA';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `device_link`
--

DROP TABLE IF EXISTS `device_link`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `device_link` (
  `source` varchar(32) NOT NULL,
  `device_id` smallint(6) NOT NULL,
  `online` tinyint(4) NOT NULL DEFAULT 0,
  `fail_streak` smallint(6) NOT NULL DEFAULT 0,
  `last_ok_ts` timestamp NULL DEFAULT NULL,
  `last_fail_ts` timestamp NULL DEFAULT NULL,
  `updated_ts` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`source`,`device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Consecutive Modbus results per device';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `em2rs_556`
--

DROP TABLE IF EXISTS `em2rs_556`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `em2rs_556` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL,
  `device_id` int(11) NOT NULL,
  `mode` varchar(16) DEFAULT NULL,
  `requested_position_steps` int(11) DEFAULT NULL,
  `actual_position_steps` int(11) DEFAULT NULL,
  `running` tinyint(1) NOT NULL DEFAULT 0,
  `alarm` tinyint(1) NOT NULL DEFAULT 0,
  `position_check` varchar(16) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_em2rs_556_ts` (`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `em2rs_556_state`
--

DROP TABLE IF EXISTS `em2rs_556_state`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `em2rs_556_state` (
  `device_id` smallint(5) unsigned NOT NULL,
  `online` tinyint(4) NOT NULL DEFAULT 0,
  `config_status` varchar(32) DEFAULT NULL,
  `pulse_per_revolution` int(11) DEFAULT NULL,
  `peak_current_raw` int(11) DEFAULT NULL,
  `peak_current_a` float DEFAULT NULL,
  `path0_mode` int(11) DEFAULT NULL,
  `target_position` int(11) DEFAULT NULL,
  `speed_rpm` int(11) DEFAULT NULL,
  `acceleration` int(11) DEFAULT NULL,
  `deceleration` int(11) DEFAULT NULL,
  `pause_time` int(11) DEFAULT NULL,
  `mode` varchar(16) DEFAULT NULL,
  `requested_position_pct` double DEFAULT NULL,
  `requested_position_steps` int(11) DEFAULT NULL,
  `actual_position_steps` int(11) DEFAULT NULL,
  `expected_delta_steps` int(11) DEFAULT NULL,
  `actual_delta_steps` int(11) DEFAULT NULL,
  `position_check` varchar(16) DEFAULT NULL,
  `running` tinyint(1) NOT NULL DEFAULT 0,
  `alarm` tinyint(1) NOT NULL DEFAULT 0,
  `alarm_text` varchar(255) DEFAULT NULL,
  `motion_phase` varchar(24) DEFAULT NULL,
  `position_valid` tinyint(1) NOT NULL DEFAULT 0,
  `trim_settle_deadline` double DEFAULT NULL,
  `updated_ts` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Current state of Leadshine EM2RS-556';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fault_log`
--

DROP TABLE IF EXISTS `fault_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `fault_log` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `source` varchar(32) NOT NULL,
  `code` varchar(32) NOT NULL,
  `severity` varchar(8) NOT NULL,
  `message` varchar(255) NOT NULL,
  `details` text DEFAULT NULL,
  `active` tinyint(4) NOT NULL DEFAULT 1,
  `ack` tinyint(4) NOT NULL DEFAULT 0,
  `cleared_ts` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ts` (`ts`),
  KEY `idx_active_ts` (`active`,`ts`),
  KEY `idx_code_ts` (`code`,`ts`),
  KEY `idx_source_ts` (`source`,`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `invt_gd20`
--

DROP TABLE IF EXISTS `invt_gd20`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `invt_gd20` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `device_id` smallint(5) unsigned NOT NULL DEFAULT 100,
  `running` tinyint(4) NOT NULL DEFAULT 0,
  `status_code` int(11) DEFAULT NULL COMMENT 'Raw Goodrive status word 0x2100: 1 forward run, 2 reverse run, 3 stop, 4 fault, 5 POFF, 6 pre-exciting',
  `fault_code` int(11) DEFAULT NULL,
  `external_stop` tinyint(4) DEFAULT NULL COMMENT '1 when S4 coast-to-stop is active',
  `pid_setpoint_kpa` float DEFAULT NULL,
  `pid_feedback_kpa` float DEFAULT NULL,
  `ai2_kpa` float DEFAULT NULL COMMENT 'AI2 in kPa. 0x300D is 0-10 V equivalent of 0-20 mA (mA = V * 2), then 4-20 mA maps to settings min_kpa/max_kpa',
  `frequency_set_hz` float DEFAULT NULL,
  `frequency_actual_hz` float DEFAULT NULL,
  `output_current_a` float DEFAULT NULL,
  `output_voltage_v` float DEFAULT NULL,
  `dc_bus_voltage_v` float DEFAULT NULL,
  `motor_speed_rpm` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ts` (`ts`),
  KEY `idx_device_ts` (`device_id`,`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Historical INVT GD20 VFD process and diagnostic values';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `invt_gd20_state`
--

DROP TABLE IF EXISTS `invt_gd20_state`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `invt_gd20_state` (
  `device_id` smallint(5) unsigned NOT NULL,
  `online` tinyint(4) NOT NULL DEFAULT 0,
  `running` tinyint(4) NOT NULL DEFAULT 0,
  `run_seconds` bigint(20) unsigned NOT NULL DEFAULT 0 COMMENT 'Seconds the drive status was RUN',
  `run_accounted_ts` datetime DEFAULT NULL COMMENT 'Last poll included in run_seconds',
  `status_code` int(11) DEFAULT NULL COMMENT 'Raw Goodrive status word 0x2100: 1 forward run, 2 reverse run, 3 stop, 4 fault, 5 POFF, 6 pre-exciting',
  `fault_code` int(11) DEFAULT NULL,
  `external_stop` tinyint(4) DEFAULT NULL COMMENT '1 when S4 coast-to-stop is active',
  `pid_setpoint_kpa` float DEFAULT NULL,
  `pid_feedback_kpa` float DEFAULT NULL,
  `ai2_kpa` float DEFAULT NULL COMMENT 'AI2 in kPa. 0x300D is 0-10 V equivalent of 0-20 mA (mA = V * 2), then 4-20 mA maps to settings min_kpa/max_kpa',
  `frequency_set_hz` float DEFAULT NULL,
  `frequency_actual_hz` float DEFAULT NULL,
  `output_current_a` float DEFAULT NULL,
  `output_voltage_v` float DEFAULT NULL,
  `dc_bus_voltage_v` float DEFAULT NULL,
  `motor_speed_rpm` int(11) DEFAULT NULL,
  `updated_ts` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Current state of INVT GD20 VFD';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `relay`
--

DROP TABLE IF EXISTS `relay`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `relay` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `r1` tinyint(4) NOT NULL DEFAULT 0,
  `r2` tinyint(4) NOT NULL DEFAULT 0,
  `r3` tinyint(4) NOT NULL DEFAULT 0,
  `r4` tinyint(4) NOT NULL DEFAULT 0,
  `r5` tinyint(4) NOT NULL DEFAULT 0,
  `r6` tinyint(4) NOT NULL DEFAULT 0,
  `r7` tinyint(4) NOT NULL DEFAULT 0,
  `r8` tinyint(4) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_ts` (`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Current relay states (r1–r8); r1=Enable PWM (FIXED), r2=Enable PID (FIXED)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `relay_cycles`
--

DROP TABLE IF EXISTS `relay_cycles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `relay_cycles` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NULL DEFAULT current_timestamp(),
  `counter` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `relay_history`
--

DROP TABLE IF EXISTS `relay_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `relay_history` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `name` varchar(32) NOT NULL,
  `state` tinyint(4) NOT NULL,
  `source` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ts` (`ts`),
  KEY `idx_name_ts` (`name`,`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Historical relay state changes for audit and diagnostics';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `relay_state`
--

DROP TABLE IF EXISTS `relay_state`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `relay_state` (
  `name` varchar(32) NOT NULL,
  `state` tinyint(4) NOT NULL DEFAULT 0,
  `source` varchar(32) DEFAULT NULL,
  `updated_ts` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `system`
--

DROP TABLE IF EXISTS `system`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `system` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `component` varchar(32) NOT NULL,
  `level` varchar(8) NOT NULL,
  `message` text NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ts` (`ts`),
  KEY `idx_component_ts` (`component`,`ts`),
  KEY `idx_level_ts` (`level`,`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='System metadata (machine type, HW version, SW version)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `system_info`
--

DROP TABLE IF EXISTS `system_info`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_info` (
  `id` tinyint(3) unsigned NOT NULL DEFAULT 1,
  `machine_type` varchar(64) NOT NULL,
  `hw_version` varchar(32) NOT NULL,
  `sw_version` varchar(32) NOT NULL,
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `temperature`
--

DROP TABLE IF EXISTS `temperature`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `temperature` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `ts` timestamp NOT NULL DEFAULT current_timestamp(),
  `t1` float DEFAULT NULL,
  `t2` float DEFAULT NULL,
  `t3` float DEFAULT NULL,
  `t4` float DEFAULT NULL,
  `t5` float DEFAULT NULL,
  `t6` float DEFAULT NULL,
  `t7` float DEFAULT NULL,
  `t8` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ts` (`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Raw temperature values read from Modbus PT100 module (°C)';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

-- Dump completed on 2026-10-23 17:31:53
