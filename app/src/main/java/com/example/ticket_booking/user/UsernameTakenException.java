package com.example.ticket_booking.user;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.CONFLICT)
public class UsernameTakenException extends RuntimeException {
    public UsernameTakenException() {
        super("用户名已存在");
    }
}