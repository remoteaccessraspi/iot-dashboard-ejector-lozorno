-- Idempotentná migrácia EM2RS-556 pre databázu ejector.
-- Vytvorí iba em2rs_556_state.
-- Nemení a nemaže existujúce tabuľky ani ich dáta.

CREATE TABLE IF NOT EXISTS em2rs_556_state (
    device_id SMALLINT UNSIGNED NOT NULL,

    online TINYINT NOT NULL DEFAULT 0,
    config_status VARCHAR(32) DEFAULT NULL,

    pulse_per_revolution INT DEFAULT NULL,
    peak_current_raw INT DEFAULT NULL,
    peak_current_a FLOAT DEFAULT NULL,

    path0_mode INT DEFAULT NULL,
    target_position INT DEFAULT NULL,
    speed_rpm INT DEFAULT NULL,
    acceleration INT DEFAULT NULL,
    deceleration INT DEFAULT NULL,
    pause_time INT DEFAULT NULL,

    updated_ts TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (device_id)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci
COMMENT='Current state of Leadshine EM2RS-556';

ALTER TABLE em2rs_556_state
  ADD COLUMN IF NOT EXISTS mode VARCHAR(16) NULL AFTER pause_time,
  ADD COLUMN IF NOT EXISTS requested_position_pct DOUBLE NULL AFTER mode,
  ADD COLUMN IF NOT EXISTS requested_position_steps INT NULL AFTER requested_position_pct,
  ADD COLUMN IF NOT EXISTS actual_position_steps INT NULL AFTER requested_position_steps,
  ADD COLUMN IF NOT EXISTS expected_delta_steps INT NULL AFTER actual_position_steps,
  ADD COLUMN IF NOT EXISTS actual_delta_steps INT NULL AFTER expected_delta_steps,
  ADD COLUMN IF NOT EXISTS position_check VARCHAR(16) NULL AFTER actual_delta_steps,
  ADD COLUMN IF NOT EXISTS running TINYINT(1) NOT NULL DEFAULT 0 AFTER position_check,
  ADD COLUMN IF NOT EXISTS alarm TINYINT(1) NOT NULL DEFAULT 0 AFTER running,
  ADD COLUMN IF NOT EXISTS alarm_text VARCHAR(255) NULL AFTER alarm,
  ADD COLUMN IF NOT EXISTS motion_phase VARCHAR(24) NULL AFTER alarm_text,
  ADD COLUMN IF NOT EXISTS position_valid TINYINT(1) NOT NULL DEFAULT 0 AFTER motion_phase,
  ADD COLUMN IF NOT EXISTS trim_settle_deadline DOUBLE NULL AFTER position_valid;

CREATE TABLE IF NOT EXISTS em2rs_556 (
  id BIGINT NOT NULL AUTO_INCREMENT,
  ts TIMESTAMP NOT NULL,
  device_id INT NOT NULL,
  mode VARCHAR(16) NULL,
  requested_position_steps INT NULL,
  actual_position_steps INT NULL,
  running TINYINT(1) NOT NULL DEFAULT 0,
  alarm TINYINT(1) NOT NULL DEFAULT 0,
  position_check VARCHAR(16) NULL,
  PRIMARY KEY (id),
  KEY idx_em2rs_556_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
