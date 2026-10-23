-- Idempotentná migrácia alarmov a warningov.
-- Nemení a nemaže existujúce tabuľky ani ich dáta.

CREATE TABLE IF NOT EXISTS device_link (
    source VARCHAR(32) NOT NULL,
    device_id SMALLINT NOT NULL,
    online TINYINT NOT NULL DEFAULT 0,
    fail_streak SMALLINT NOT NULL DEFAULT 0,
    last_ok_ts TIMESTAMP NULL DEFAULT NULL,
    last_fail_ts TIMESTAMP NULL DEFAULT NULL,
    updated_ts TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (source, device_id)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci
COMMENT='Consecutive Modbus results per device';

CREATE TABLE IF NOT EXISTS alarm_state (
    code VARCHAR(32) NOT NULL,
    source VARCHAR(32) NOT NULL,
    device_id SMALLINT NOT NULL DEFAULT 0,
    class ENUM('ALARM','WARNING') NOT NULL,
    message VARCHAR(255) NOT NULL,
    details TEXT NULL,
    condition_on TINYINT NOT NULL DEFAULT 1,
    latched TINYINT NOT NULL DEFAULT 0,
    inhibit_run TINYINT NOT NULL DEFAULT 0,
    release_policy ENUM('NONE','ACK','ACK_AND_HOLD_RUN') NOT NULL DEFAULT 'NONE',
    event_id BIGINT UNSIGNED NULL,
    raised_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ack_ts TIMESTAMP NULL DEFAULT NULL,
    ack_source VARCHAR(32) NULL,
    cleared_ts TIMESTAMP NULL DEFAULT NULL,
    updated_ts TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (code, source, device_id)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci
COMMENT='One open alarm or warning';

CREATE TABLE IF NOT EXISTS alarm_event (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    code VARCHAR(32) NOT NULL,
    source VARCHAR(32) NOT NULL,
    device_id SMALLINT NOT NULL DEFAULT 0,
    class ENUM('ALARM','WARNING') NOT NULL,
    message VARCHAR(255) NOT NULL,
    details TEXT NULL,
    inhibit_run TINYINT NOT NULL DEFAULT 0,
    release_policy ENUM('NONE','ACK','ACK_AND_HOLD_RUN') NOT NULL DEFAULT 'NONE',
    ack_ts TIMESTAMP NULL DEFAULT NULL,
    cleared_ts TIMESTAMP NULL DEFAULT NULL,
    PRIMARY KEY (id),
    KEY idx_open (code, source, device_id, cleared_ts),
    KEY idx_ts (ts)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci
COMMENT='Alarm and warning occurrences';
