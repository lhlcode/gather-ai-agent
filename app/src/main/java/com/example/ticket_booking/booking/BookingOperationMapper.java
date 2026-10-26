package com.example.ticket_booking.booking;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface BookingOperationMapper {
    @Insert("""
            INSERT INTO booking_operations (
                user_id, operation_id, event_id
            )
            VALUES (#{userId}, #{operationId}, #{eventId})
            ON DUPLICATE KEY UPDATE
                operation_id = booking_operations.operation_id
            """)
    int claim(
            @Param("userId") long userId,
            @Param("operationId") String operationId,
            @Param("eventId") long eventId);

    @Select("""
            SELECT operation_id AS operationId,
                   event_id AS eventId,
                   order_id AS orderId
            FROM booking_operations
            WHERE user_id = #{userId}
              AND operation_id = #{operationId}
            FOR UPDATE
            """)
    BookingOperation findForUpdate(
            @Param("userId") long userId,
            @Param("operationId") String operationId);

    @Update("""
            UPDATE booking_operations
            SET order_id = #{orderId}
            WHERE user_id = #{userId}
              AND operation_id = #{operationId}
              AND order_id IS NULL
            """)
    int attachOrder(
            @Param("userId") long userId,
            @Param("operationId") String operationId,
            @Param("orderId") long orderId);

    @Select("""
            SELECT id, event_id AS eventId, status
            FROM booking_orders
            WHERE id = #{orderId}
              AND user_id = #{userId}
              AND event_id = #{eventId}
            FOR UPDATE
            """)
    OrderView findOwnedOrder(
            @Param("orderId") long orderId,
            @Param("userId") long userId,
            @Param("eventId") long eventId);
}