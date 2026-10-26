package com.example.ticket_booking.booking;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/events/{eventId}/booking-operations")
public class BookingOperationController {
    private final BookingOperationService service;

    public BookingOperationController(
            BookingOperationService service) {
        this.service = service;
    }

    @PostMapping
    public ResponseEntity<BookingOperationService.Result> book(
            @PathVariable long eventId,
            @RequestHeader("Idempotency-Key") String operationId,
            @AuthenticationPrincipal Jwt jwt) {
        long userId = Long.parseLong(jwt.getSubject());

        BookingOperationService.Result result =
                service.book(eventId, userId, operationId);

        return ResponseEntity.status(
                result.replayed()
                        ? HttpStatus.OK
                        : HttpStatus.CREATED
        ).body(result);
    }
}