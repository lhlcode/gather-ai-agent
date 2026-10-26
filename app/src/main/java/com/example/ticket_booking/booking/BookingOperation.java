package com.example.ticket_booking.booking;

public class BookingOperation {
    private String operationId;
    private Long eventId;
    private Long orderId;

    public String getOperationId() { return operationId; }
    public void setOperationId(String operationId) {
        this.operationId = operationId;
    }

    public Long getEventId() { return eventId; }
    public void setEventId(Long eventId) {
        this.eventId = eventId;
    }

    public Long getOrderId() { return orderId; }
    public void setOrderId(Long orderId) {
        this.orderId = orderId;
    }
}