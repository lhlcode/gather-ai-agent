package com.example.ticket_booking.booking;

public class OrderView {
    private Long id;
    private Long eventId;
    private String eventTitle;
    private String status;
    private String expiresAtUtc;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getEventId() { return eventId; }
    public void setEventId(Long eventId) { this.eventId = eventId; }

    public String getEventTitle() { return eventTitle; }
    public void setEventTitle(String eventTitle) { this.eventTitle = eventTitle; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getExpiresAtUtc() { return expiresAtUtc; }
    public void setExpiresAtUtc(String expiresAtUtc) {
        this.expiresAtUtc = expiresAtUtc;
    }
}