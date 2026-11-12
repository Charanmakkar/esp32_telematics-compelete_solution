-- NavSphere six-channel schema. Canonical installation: alembic upgrade head.
-- Create the database and restricted account separately. No credentials are embedded.
SET NAMES utf8mb4;

CREATE TABLE audit_events (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	created_at DATETIME(3) NOT NULL, 
	actor VARCHAR(64) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	details JSON NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_audit_events_created_at ON audit_events (created_at);

CREATE TABLE devices (
	device_id VARCHAR(64) NOT NULL, 
	last_seen DATETIME(3), 
	online BOOL NOT NULL, 
	source VARCHAR(16) NOT NULL, 
	boot_id VARCHAR(64), 
	control_a INTEGER, 
	control_b INTEGER, 
	PRIMARY KEY (device_id)
);

CREATE TABLE telemetry_readings (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	device_id VARCHAR(64) NOT NULL, 
	boot_id VARCHAR(64) NOT NULL, 
	sequence_number BIGINT UNSIGNED NOT NULL, 
	timestamp_ms BIGINT UNSIGNED, 
	observed_ms BIGINT UNSIGNED NOT NULL, 
	received_at DATETIME(3) NOT NULL, 
	persisted_at DATETIME(3) NOT NULL, 
	analog_1 INTEGER UNSIGNED NOT NULL, 
	analog_2 INTEGER UNSIGNED NOT NULL, 
	analog_3 INTEGER UNSIGNED NOT NULL, 
	analog_4 INTEGER UNSIGNED NOT NULL, 
	analog_5 INTEGER UNSIGNED NOT NULL, 
	analog_6 INTEGER UNSIGNED NOT NULL, 
	valid_mask SMALLINT UNSIGNED NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_device_observed ON telemetry_readings (device_id, observed_ms);
CREATE INDEX ix_device_received ON telemetry_readings (device_id, received_at, id);
CREATE INDEX ix_device_timestamp ON telemetry_readings (device_id, timestamp_ms);
CREATE INDEX ix_received_retention ON telemetry_readings (received_at);
CREATE UNIQUE INDEX uq_device_boot_sequence ON telemetry_readings (device_id, boot_id, sequence_number);

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(64) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	`role` VARCHAR(16) NOT NULL, 
	must_change_password BOOL NOT NULL, 
	active BOOL NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
);

CREATE TABLE commands (
	command_id VARCHAR(36) NOT NULL, 
	device_id VARCHAR(64) NOT NULL, 
	`key` VARCHAR(1) NOT NULL, 
	value INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	reason VARCHAR(255) NOT NULL, 
	boot_id VARCHAR(64), 
	created_at DATETIME(3) NOT NULL, 
	expires_at DATETIME(3) NOT NULL, 
	updated_at DATETIME(3) NOT NULL, 
	user_id INTEGER NOT NULL, 
	PRIMARY KEY (command_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_commands_device_id ON commands (device_id);
CREATE INDEX ix_commands_expires_at ON commands (expires_at);

CREATE TABLE login_sessions (
	token_hash VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	csrf_token VARCHAR(64) NOT NULL, 
	expires_at DATETIME(3) NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_login_sessions_expires_at ON login_sessions (expires_at);
