package com.example.ticket_booking.booking;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.CONFLICT)
public class ActiveBookingExistsException extends RuntimeException {
    public ActiveBookingExistsException() {
        super("该活动已有待支付或已支付订单");
    }
}