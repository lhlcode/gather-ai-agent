package com.example.ticket_booking.event;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
@RestController
@RequestMapping("/events")
public class EventController {
    private final EventService eventService;

    public EventController(EventService eventService) {
        this.eventService = eventService;
    }

    @GetMapping
    public List<EventSummary> list() {
        return eventService.listPublished();
    }

    @GetMapping("/{id}")
    public ResponseEntity<EventSummary> findById(@PathVariable long id) {
        EventSummary event = eventService.findPublishedById(id);
        if(event == null){
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(event);

    }
}