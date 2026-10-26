package com.example.ticket_booking.event;

import java.time.Instant;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/admin/events")
public class EventAdminController {
    private final EventAdminService eventAdminService;

    public EventAdminController(EventAdminService eventAdminService) {
        this.eventAdminService = eventAdminService;
    }

    @PostMapping
    public ResponseEntity<EventStatusResponse> create(
            @Valid @RequestBody CreateEventRequest request) {
        long eventId = eventAdminService.createDraft(
                request.title(),
                request.totalQuota(),
                request.registrationStartAtUtc(),
                request.registrationEndAtUtc());

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(new EventStatusResponse(eventId, "DRAFT"));
    }

    @PostMapping("/{eventId}/publish")
    public EventStatusResponse publish(@PathVariable long eventId) {
        eventAdminService.publish(eventId);
        return new EventStatusResponse(eventId, "PUBLISHED");
    }

    public record CreateEventRequest(
            @NotBlank @Size(max = 120) String title,
            @Min(1) int totalQuota,
            @NotNull Instant registrationStartAtUtc,
            @NotNull Instant registrationEndAtUtc) {}

    public record EventStatusResponse(long eventId, String status) {}
}