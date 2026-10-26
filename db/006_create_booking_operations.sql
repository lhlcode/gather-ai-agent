CREATE TABLE IF NOT EXISTS booking_operations (
    user_id BIGINT UNSIGNED NOT NULL,
    operation_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    event_id BIGINT UNSIGNED NOT NULL,
    order_id BIGINT UNSIGNED NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    PRIMARY KEY (user_id, operation_id),
    UNIQUE KEY uk_booking_operations_order (order_id),

    CONSTRAINT fk_booking_operations_user
        FOREIGN KEY (user_id) REFERENCES users (id),

    CONSTRAINT fk_booking_operations_order
        FOREIGN KEY (order_id) REFERENCES booking_orders (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;