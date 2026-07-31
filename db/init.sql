-- ============================================
-- IoT Dashboard - MariaDB initialization
-- ============================================

-- create database if not exists
CREATE DATABASE IF NOT EXISTS ejector
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE ejector;

-- ============================================
-- TEMPERATURE TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS temperature (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    t1 FLOAT,
    t2 FLOAT,
    t3 FLOAT,
    t4 FLOAT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_temperature_ts
ON temperature(ts);

-- ============================================
-- CURRENT LOOP TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS current_loop (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    i1 FLOAT,
    i2 FLOAT,
    i3 FLOAT,
    i4 FLOAT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_current_loop_ts
ON current_loop(ts);

-- ============================================
-- CONVERSION TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS conversion_table (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    p1 FLOAT,
    p2 FLOAT,
    p3 FLOAT,
    p4 FLOAT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- RELAY STATE
-- ============================================

CREATE TABLE IF NOT EXISTS relay (
    id INT PRIMARY KEY,
    name VARCHAR(50),
    state BOOLEAN DEFAULT FALSE
);

-- ============================================
-- RELAY HISTORY
-- ============================================

CREATE TABLE IF NOT EXISTS relay_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    relay_id INT,
    state BOOLEAN,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP
);
