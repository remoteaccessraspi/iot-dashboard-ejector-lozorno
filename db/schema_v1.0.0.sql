/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19-11.8.3-MariaDB, for debian-linux-gnu (aarch64)
--
-- Host: localhost    Database: ejector
-- ------------------------------------------------------
-- Server version	11.8.3-MariaDB-0+deb13u1 from Debian

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
) ENGINE=InnoDB AUTO_INCREMENT=154 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Control parameters written by HMI or system logic';
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
  KEY `idx_ts` (`ts`),
  KEY `idx_current_loop_id` (`current_loop_id`)
) ENGINE=InnoDB AUTO_INCREMENT=104293 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Converted physical quantities calculated from current_loop';
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
) ENGINE=InnoDB AUTO_INCREMENT=162488 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Raw current loop inputs (4–20 mA), stored in mA';
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
) ENGINE=InnoDB AUTO_INCREMENT=431310 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Current relay states (r1–r8); r1=Enable PWM (FIXED), r2=Enable PID (FIXED)';
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
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Historical relay state changes for audit and diagnostics';
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
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='System metadata (machine type, HW version, SW version)';
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
) ENGINE=InnoDB AUTO_INCREMENT=162624 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Raw temperature values read from Modbus PT100 module (°C)';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

-- Dump completed on 2026-03-09 11:40:25
