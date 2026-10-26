package com.example.ticket_booking.booking;

import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
class OrderRaceTests {

    @Autowired
    private BookingService bookingService;

    @Autowired
    private OrderActionService orderActionService;

    @Autowired
    private OrderExpiryService orderExpiryService;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void paymentAndCancellationCannotBothWin() throws Exception {
        Fixture fixture = createFixture();
        ExecutorService pool = Executors.newFixedThreadPool(2);

        try {
            assertEquals(0, availableQuota(fixture.eventId()));

            CountDownLatch start = new CountDownLatch(1);

            Future<Boolean> payment = pool.submit(() -> {
                start.await();
                try {
                    orderActionService.pay(fixture.orderId(), fixture.userId());
                    return true;
                } catch (OrderStateConflictException e) {
                    return false;
                }
            });

            Future<Boolean> cancellation = pool.submit(() -> {
                start.await();
                try {
                    orderActionService.cancel(fixture.orderId(), fixture.userId());
                    return true;
                } catch (OrderStateConflictException e) {
                    return false;
                }
            });

            start.countDown();

            boolean paid = payment.get(30, TimeUnit.SECONDS);
            boolean cancelled = cancellation.get(30, TimeUnit.SECONDS);

            assertTrue(paid ^ cancelled, "支付和取消必须恰好成功一个");
            assertEquals(paid ? "PAID" : "CANCELLED", status(fixture.orderId()));
            assertEquals(paid ? 0 : 1, availableQuota(fixture.eventId()));
        } finally {
            pool.shutdownNow();
            cleanup(fixture.eventId(), fixture.userId());
        }
    }

    @Test
    void cancellationAndExpiryReleaseOnlyOneSeat() throws Exception {
        Fixture fixture = createFixture();
        ExecutorService pool = Executors.newFixedThreadPool(2);

        try {
            assertEquals(0, availableQuota(fixture.eventId()));

            // 只修改本测试创建的订单，使它符合过期条件。
            jdbcTemplate.update("""
                    UPDATE booking_orders
                    SET expires_at = NOW(3) - INTERVAL 1 SECOND
                    WHERE id = ?
                    """, fixture.orderId());

            CountDownLatch start = new CountDownLatch(1);

            Future<Boolean> cancellation = pool.submit(() -> {
                start.await();
                try {
                    orderActionService.cancel(fixture.orderId(), fixture.userId());
                    return true;
                } catch (OrderStateConflictException e) {
                    return false;
                }
            });

            Future<Boolean> expiry = pool.submit(() -> {
                start.await();
                return orderExpiryService.expireOne(fixture.orderId());
            });

            start.countDown();
            cancellation.get(30, TimeUnit.SECONDS);
            expiry.get(30, TimeUnit.SECONDS);

            String finalStatus = status(fixture.orderId());
            assertTrue(
                    finalStatus.equals("CANCELLED") || finalStatus.equals("EXPIRED"),
                    "最终状态应为已取消或已过期"
            );
            assertEquals(1, availableQuota(fixture.eventId()));

            // 再执行一次关单也不能再次归还名额。
            assertFalse(orderExpiryService.expireOne(fixture.orderId()));
            assertEquals(1, availableQuota(fixture.eventId()));
        } finally {
            pool.shutdownNow();
            cleanup(fixture.eventId(), fixture.userId());
        }
    }

    private Fixture createFixture() {
        Long userId = null;
        Long eventId = null;

        try {
            String username = "race_" + UUID.randomUUID().toString().replace("-", "");
            jdbcTemplate.update(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    username, "TEST_ONLY_NO_LOGIN"
            );
            userId = jdbcTemplate.queryForObject(
                    "SELECT id FROM users WHERE username = ?",
                    Long.class, username
            );

            String title = "Order race " + UUID.randomUUID();
            jdbcTemplate.update("""
                    INSERT INTO events (
                        title, total_quota, available_quota,
                        registration_start_at, registration_end_at, status
                    ) VALUES (
                        ?, 1, 1,
                        NOW(3) - INTERVAL 1 HOUR,
                        NOW(3) + INTERVAL 1 DAY,
                        'PUBLISHED'
                    )
                    """, title);
            eventId = jdbcTemplate.queryForObject(
                    "SELECT id FROM events WHERE title = ?",
                    Long.class, title
            );

            long orderId = bookingService.book(eventId, userId);
            return new Fixture(userId, eventId, orderId);
        } catch (RuntimeException e) {
            cleanup(eventId, userId);
            throw e;
        }
    }

    private String status(long orderId) {
        return jdbcTemplate.queryForObject(
                "SELECT status FROM booking_orders WHERE id = ?",
                String.class, orderId
        );
    }

    private int availableQuota(long eventId) {
        return jdbcTemplate.queryForObject(
                "SELECT available_quota FROM events WHERE id = ?",
                Integer.class, eventId
        );
    }

    private void cleanup(Long eventId, Long userId) {
        if (eventId != null) {
            jdbcTemplate.update(
                    "DELETE FROM booking_orders WHERE event_id = ?", eventId
            );
            jdbcTemplate.update("DELETE FROM events WHERE id = ?", eventId);
        }
        if (userId != null) {
            jdbcTemplate.update("DELETE FROM users WHERE id = ?", userId);
        }
    }

    private record Fixture(long userId, long eventId, long orderId) {}
}