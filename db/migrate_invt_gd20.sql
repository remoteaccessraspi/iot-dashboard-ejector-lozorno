-- Idempotentná migrácia INVT GD20 pre databázu ejector.
-- Vytvorí iba invt_gd20_state a invt_gd20.
-- Nemení a nemaže existujúce tabuľky ani ich dáta.
-- Bezpečné spustiť opakovane.

CREATE TABLE IF NOT EXISTS invt_gd20_state (
    device_id SMALLINT UNSIGNED NOT NULL,

    online TINYINT NOT NULL DEFAULT 0,
    running TINYINT NOT NULL DEFAULT 0,
    status_code INT DEFAULT NULL COMMENT 'Raw Goodrive status word 0x2100: 1 forward run, 2 reverse run, 3 stop, 4 fault, 5 POFF, 6 pre-exciting',
    fault_code INT DEFAULT NULL,

    pid_setpoint_kpa FLOAT DEFAULT NULL,
    pid_feedback_kpa FLOAT DEFAULT NULL,
    ai2_kpa FLOAT DEFAULT NULL COMMENT 'AI2 in kPa. 0x300D is 0-10 V equivalent of 0-20 mA (mA = V * 2), then 4-20 mA maps to settings min_kpa/max_kpa',

    frequency_set_hz FLOAT DEFAULT NULL,
    frequency_actual_hz FLOAT DEFAULT NULL,

    output_current_a FLOAT DEFAULT NULL,
    output_voltage_v FLOAT DEFAULT NULL,
    dc_bus_voltage_v FLOAT DEFAULT NULL,
    motor_speed_rpm INT DEFAULT NULL,

    updated_ts TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (device_id)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci
COMMENT='Current state of INVT GD20 VFD';

CREATE TABLE IF NOT EXISTS invt_gd20 (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    device_id SMALLINT UNSIGNED NOT NULL DEFAULT 100,

    running TINYINT NOT NULL DEFAULT 0,
    status_code INT DEFAULT NULL COMMENT 'Raw Goodrive status word 0x2100: 1 forward run, 2 reverse run, 3 stop, 4 fault, 5 POFF, 6 pre-exciting',
    fault_code INT DEFAULT NULL,

    pid_setpoint_kpa FLOAT DEFAULT NULL,
    pid_feedback_kpa FLOAT DEFAULT NULL,
    ai2_kpa FLOAT DEFAULT NULL COMMENT 'AI2 in kPa. 0x300D is 0-10 V equivalent of 0-20 mA (mA = V * 2), then 4-20 mA maps to settings min_kpa/max_kpa',

    frequency_set_hz FLOAT DEFAULT NULL,
    frequency_actual_hz FLOAT DEFAULT NULL,

    output_current_a FLOAT DEFAULT NULL,
    output_voltage_v FLOAT DEFAULT NULL,
    dc_bus_voltage_v FLOAT DEFAULT NULL,
    motor_speed_rpm INT DEFAULT NULL,

    PRIMARY KEY (id),
    KEY idx_ts (ts),
    KEY idx_device_ts (device_id, ts)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci
COMMENT='Historical INVT GD20 VFD process and diagnostic values';

-- Existujúce inštalácie: CREATE TABLE IF NOT EXISTS stĺpec nepridá.
-- 0x300D * 0.01 = V na škále 0–10 V ↔ 0–20 mA, potom 4–20 mA → min_kpa..max_kpa.
ALTER TABLE invt_gd20_state
    ADD COLUMN IF NOT EXISTS ai2_kpa FLOAT DEFAULT NULL
        COMMENT 'AI2 in kPa. 0x300D is 0-10 V equivalent of 0-20 mA (mA = V * 2), then 4-20 mA maps to settings min_kpa/max_kpa'
        AFTER pid_feedback_kpa;

ALTER TABLE invt_gd20
    ADD COLUMN IF NOT EXISTS ai2_kpa FLOAT DEFAULT NULL
        COMMENT 'AI2 in kPa. 0x300D is 0-10 V equivalent of 0-20 mA (mA = V * 2), then 4-20 mA maps to settings min_kpa/max_kpa'
        AFTER pid_feedback_kpa;

ALTER TABLE invt_gd20_state
    MODIFY COLUMN ai2_kpa FLOAT DEFAULT NULL
        COMMENT 'AI2 in kPa. 0x300D is 0-10 V equivalent of 0-20 mA (mA = V * 2), then 4-20 mA maps to settings min_kpa/max_kpa';

ALTER TABLE invt_gd20
    MODIFY COLUMN ai2_kpa FLOAT DEFAULT NULL
        COMMENT 'AI2 in kPa. 0x300D is 0-10 V equivalent of 0-20 mA (mA = V * 2), then 4-20 mA maps to settings min_kpa/max_kpa';

ALTER TABLE invt_gd20_state
    ADD COLUMN IF NOT EXISTS status_code INT DEFAULT NULL
        COMMENT 'Raw Goodrive status word 0x2100: 1 forward run, 2 reverse run, 3 stop, 4 fault, 5 POFF, 6 pre-exciting'
        AFTER running;

ALTER TABLE invt_gd20
    ADD COLUMN IF NOT EXISTS status_code INT DEFAULT NULL
        COMMENT 'Raw Goodrive status word 0x2100: 1 forward run, 2 reverse run, 3 stop, 4 fault, 5 POFF, 6 pre-exciting'
        AFTER running;

ALTER TABLE invt_gd20_state
    DROP COLUMN IF EXISTS ai2_value;

ALTER TABLE invt_gd20
    DROP COLUMN IF EXISTS ai2_value;

INSERT IGNORE INTO invt_gd20_state (
    device_id,
    online,
    running
)
VALUES (
    100,
    0,
    0
);
