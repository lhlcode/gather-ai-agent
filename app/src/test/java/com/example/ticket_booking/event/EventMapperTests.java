package com.example.ticket_booking.event;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringBootTest
@Transactional
class EventMapperTests {

    @Autowired
    private EventMapper eventMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void reservesOnlyOneAvailableSeat() {
        jdbcTemplate.update("""
                INSERT INTO events (
                    title, total_quota, available_quota,
                    registration_start_at, registration_end_at, status
                ) VALUES (
                    'Mapper test', 1, 1,
                    NOW(3) - INTERVAL 1 HOUR, NOW(3) + INTERVAL 1 DAY, 'PUBLISHED'
                )
                """);

        Long eventId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        assertNotNull(eventId);

        assertEquals(1, eventMapper.reserveOne(eventId));
        assertEquals(0, eventMapper.reserveOne(eventId));
        assertEquals(0, jdbcTemplate.queryForObject(
                "SELECT available_quota FROM events WHERE id = ?", Integer.class, eventId));
    }
}
