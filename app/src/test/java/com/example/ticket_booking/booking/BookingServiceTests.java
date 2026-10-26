package com.example.ticket_booking.booking;

import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
class BookingServiceTests {

    @Autowired
    private BookingService bookingService;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void duplicateBookingRollsBackTheReservedSeat() {
        Long createdUserId = null;
        Long createdEventId = null;
        try {
            String username = "booking_test_" + UUID.randomUUID().toString().replace("-", "");
            jdbcTemplate.update(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    username, "TEST_ONLY_NO_LOGIN");
            createdUserId = jdbcTemplate.queryForObject(
                    "SELECT id FROM users WHERE username = ?", Long.class, username);

            String title = "Booking service test " + UUID.randomUUID();
            jdbcTemplate.update("""
                    INSERT INTO events (
                        title, total_quota, available_quota,
                        registration_start_at, registration_end_at, status
                    ) VALUES (
                        ?, 2, 2,
                        NOW(3) - INTERVAL 1 HOUR, NOW(3) + INTERVAL 1 DAY, 'PUBLISHED'
                    )
                    """, title);
            createdEventId = jdbcTemplate.queryForObject(
                    "SELECT id FROM events WHERE title = ?", Long.class, title);

            long userId = createdUserId;
            long eventId = createdEventId;
            long firstOrderId = bookingService.book(eventId, userId);
            assertTrue(firstOrderId > 0);
            assertEquals(1, availableQuota(eventId));

            assertThrows(ActiveBookingExistsException.class,
                    () -> bookingService.book(eventId, userId));
            assertEquals(1, availableQuota(eventId));
            assertEquals(1, jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM booking_orders WHERE event_id = ? AND user_id = ?",
                    Integer.class, eventId, userId));
        } finally {
            if (createdEventId != null) {
                jdbcTemplate.update("DELETE FROM booking_orders WHERE event_id = ?", createdEventId);
                jdbcTemplate.update("DELETE FROM events WHERE id = ?", createdEventId);
            }
            if (createdUserId != null) {
                jdbcTemplate.update("DELETE FROM users WHERE id = ?", createdUserId);
            }
        }
    }

    private int availableQuota(long eventId) {
        return jdbcTemplate.queryForObject(
                "SELECT available_quota FROM events WHERE id = ?", Integer.class, eventId);
    }
}
