package com.example.ticket_booking.booking;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.CONFLICT)
public class BookingUnavailableException extends RuntimeException {
    public BookingUnavailableException() {
        super("活动当前不可报名");
    }
}