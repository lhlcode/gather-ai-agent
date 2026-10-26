CREATE TABLE events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    title VARCHAR(120) NOT NULL,
    total_quota INT UNSIGNED NOT NULL,
    available_quota INT UNSIGNED NOT NULL,
    registration_start_at DATETIME(3) NOT NULL,
    registration_end_at DATETIME(3) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    CONSTRAINT chk_events_total_quota CHECK (total_quota > 0),
    CONSTRAINT chk_events_available_quota CHECK (available_quota <= total_quota),
    CONSTRAINT chk_events_registration_window CHECK (registration_start_at < registration_end_at),
    CONSTRAINT chk_events_status CHECK (status IN ('DRAFT', 'PUBLISHED', 'CLOSED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
