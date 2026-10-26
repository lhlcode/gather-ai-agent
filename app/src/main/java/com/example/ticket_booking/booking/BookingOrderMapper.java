package com.example.ticket_booking.booking;

import java.util.List;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface BookingOrderMapper {

    @Insert("""
            INSERT INTO booking_orders (event_id, user_id, status, expires_at)
            VALUES (#{eventId}, #{userId}, 'UNPAID', NOW(3) + INTERVAL 15 MINUTE)
            """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(BookingOrder order);

    @Select("""
            SELECT o.id,
                   o.event_id AS eventId,
                   e.title AS eventTitle,
                   o.status,
                   DATE_FORMAT(
                       o.expires_at,
                       '%Y-%m-%dT%H:%i:%s.%fZ'
                   ) AS expiresAtUtc
            FROM booking_orders o
            JOIN events e ON e.id = o.event_id
            WHERE o.user_id = #{userId}
            ORDER BY o.id DESC
            """)
    List<OrderView> findByUserId(@Param("userId") long userId);

    @Select("""
            SELECT id
            FROM booking_orders
            WHERE status = 'UNPAID'
              AND expires_at <= NOW(3)
            ORDER BY expires_at, id
            LIMIT 100
            """)
    List<Long> findExpiredUnpaidIds();

    @Select("""
            SELECT event_id
            FROM booking_orders
            WHERE id = #{orderId}
            """)
    Long findEventId(@Param("orderId") long orderId);

    @Update("""
            UPDATE booking_orders
            SET status = 'EXPIRED'
            WHERE id = #{orderId}
              AND status = 'UNPAID'
              AND expires_at <= NOW(3)
            """)
    int markExpiredIfOverdue(@Param("orderId") long orderId);
    @Select("""
            SELECT event_id
            FROM booking_orders
            WHERE id = #{orderId}
              AND user_id = #{userId}
            """)
    Long findEventIdForUser(
            @Param("orderId") long orderId,
            @Param("userId") long userId);

    @Update("""
            UPDATE booking_orders
            SET status = 'PAID'
            WHERE id = #{orderId}
              AND user_id = #{userId}
              AND status = 'UNPAID'
              AND expires_at > NOW(3)
            """)
    int markPaidIfValid(
            @Param("orderId") long orderId,
            @Param("userId") long userId);

    @Update("""
            UPDATE booking_orders
            SET status = 'CANCELLED'
            WHERE id = #{orderId}
              AND user_id = #{userId}
              AND status = 'UNPAID'
            """)
    int markCancelledIfUnpaid(
            @Param("orderId") long orderId,
            @Param("userId") long userId);
}