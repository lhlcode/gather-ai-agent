package com.example.ticket_booking.event;

import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface EventMapper {
    @Select("""
        SELECT id
        FROM events
        WHERE id = #{eventId}
        FOR UPDATE
        """)
    Long lockById(@Param("eventId") long eventId);

    @Update("""
        UPDATE events
        SET available_quota = available_quota + 1
        WHERE id = #{eventId}
          AND available_quota < total_quota
        """)
    int releaseOne(@Param("eventId") long eventId);
    @Select("""
        SELECT id, title,
               total_quota AS totalQuota,
               available_quota AS availableQuota,
               DATE_FORMAT(registration_start_at,
                   '%Y-%m-%dT%H:%i:%s.%fZ') AS registrationStartAtUtc,
               DATE_FORMAT(registration_end_at,
                   '%Y-%m-%dT%H:%i:%s.%fZ') AS registrationEndAtUtc
        FROM events
        WHERE status = 'PUBLISHED'
        ORDER BY id DESC
        """)
    List<EventSummary> findPublished();

    @Update("""
            UPDATE events
            SET available_quota = available_quota - 1
            WHERE id = #{eventId}
              AND status = 'PUBLISHED'
              AND registration_start_at <= NOW(3)
              AND registration_end_at > NOW(3)
              AND available_quota > 0
            """)
    int reserveOne(@Param("eventId") long eventId);

    @Select("""
        SELECT id, title,
               total_quota AS totalQuota,
               available_quota AS availableQuota,
               DATE_FORMAT(registration_start_at,
                   '%Y-%m-%dT%H:%i:%s.%fZ') AS registrationStartAtUtc,
               DATE_FORMAT(registration_end_at,
                   '%Y-%m-%dT%H:%i:%s.%fZ') AS registrationEndAtUtc
        FROM events
        WHERE id = #{eventId}
          AND status = 'PUBLISHED'
        """)
    EventSummary findPublishedById(@Param("eventId") long eventId);

    @Insert("""
            INSERT INTO events (
                title, total_quota, available_quota,
                registration_start_at, registration_end_at, status
            )
            VALUES (
                #{title}, #{totalQuota}, #{totalQuota},
                #{registrationStartAtUtc}, #{registrationEndAtUtc}, 'DRAFT'
            )
            """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insertDraft(EventDraft draft);

    @Select("""
            SELECT status FROM events WHERE id = #{eventId}
            """)
    String findStatusById(@Param("eventId") long eventId);

    @Update("""
            UPDATE events
            SET status = 'PUBLISHED'
            WHERE id = #{eventId}
              AND status = 'DRAFT'
              AND registration_end_at > NOW(3)
            """)
    int publishDraft(@Param("eventId") long eventId);
}
