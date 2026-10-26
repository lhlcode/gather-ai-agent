package com.example.ticket_booking.booking;

public class BookingOrder {

    private Long id;
    private final long eventId;
    private final long userId;

    public BookingOrder(long eventId, long userId) {
        this.eventId = eventId;
        this.userId = userId;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public long getEventId() {
        return eventId;
    }

    public long getUserId() {
        return userId;
    }
}
