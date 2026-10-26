CREATE TABLE booking_orders (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    event_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(16) COLLATE utf8mb4_0900_bin NOT NULL DEFAULT 'UNPAID',
    expires_at DATETIME(3) NOT NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    active_marker TINYINT GENERATED ALWAYS AS (
        CASE WHEN status IN ('UNPAID', 'PAID') THEN 1 ELSE NULL END
    ) STORED,
    PRIMARY KEY (id),
    UNIQUE KEY uk_booking_orders_effective (event_id, user_id, active_marker),
    KEY idx_booking_orders_user_created (user_id, created_at),
    CONSTRAINT fk_booking_orders_event FOREIGN KEY (event_id) REFERENCES events (id),
    CONSTRAINT fk_booking_orders_user FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT chk_booking_orders_status CHECK (status IN ('UNPAID', 'PAID', 'CANCELLED', 'EXPIRED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
