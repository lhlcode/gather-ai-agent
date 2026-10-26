package com.example.ticket_booking.event;

import java.time.LocalDateTime;

public class EventDraft {
    private Long id;
    private final String title;
    private final int totalQuota;
    private final LocalDateTime registrationStartAtUtc;
    private final LocalDateTime registrationEndAtUtc;

    public EventDraft(
            String title,
            int totalQuota,
            LocalDateTime registrationStartAtUtc,
            LocalDateTime registrationEndAtUtc) {
        this.title = title;
        this.totalQuota = totalQuota;
        this.registrationStartAtUtc = registrationStartAtUtc;
        this.registrationEndAtUtc = registrationEndAtUtc;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getTitle() {
        return title;
    }

    public int getTotalQuota() {
        return totalQuota;
    }

    public LocalDateTime getRegistrationStartAtUtc() {
        return registrationStartAtUtc;
    }

    public LocalDateTime getRegistrationEndAtUtc() {
        return registrationEndAtUtc;
    }
}