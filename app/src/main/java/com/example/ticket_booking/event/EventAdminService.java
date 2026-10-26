package com.example.ticket_booking.event;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class EventAdminService {
    private final EventMapper eventMapper;
    private final EventService eventService;

    public EventAdminService(EventMapper eventMapper, EventService eventService) {
        this.eventMapper = eventMapper;
        this.eventService = eventService;
    }

    public long createDraft(
            String title,
            int totalQuota,
            Instant registrationStartAtUtc,
            Instant registrationEndAtUtc) {
        if (!registrationStartAtUtc.isBefore(registrationEndAtUtc)
                || !registrationEndAtUtc.isAfter(Instant.now())) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "报名结束时间必须晚于开始时间和当前时间");
        }

        EventDraft draft = new EventDraft(
                title.trim(),
                totalQuota,
                LocalDateTime.ofInstant(registrationStartAtUtc, ZoneOffset.UTC),
                LocalDateTime.ofInstant(registrationEndAtUtc, ZoneOffset.UTC));

        if (eventMapper.insertDraft(draft) != 1 || draft.getId() == null) {
            throw new IllegalStateException("活动创建失败");
        }

        return draft.getId();
    }

    public void publish(long eventId) {
        if (eventMapper.findStatusById(eventId) == null) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND, "活动不存在");
        }

        if (eventMapper.publishDraft(eventId) != 1) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    "活动不是草稿，或报名时间已经结束");
        }

        eventService.evictPublishedDetail(eventId);
    }
}