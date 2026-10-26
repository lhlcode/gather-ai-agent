package com.example.ticket_booking.booking;

import java.util.List;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/orders")
public class OrderController {
    private final BookingService bookingService;
    private final OrderActionService orderActionService;

    public OrderController(
            BookingService bookingService,
            OrderActionService orderActionService) {
        this.bookingService = bookingService;
        this.orderActionService = orderActionService;
    }

    @GetMapping
    public List<OrderView> mine(@AuthenticationPrincipal Jwt jwt) {
        long userId = Long.parseLong(jwt.getSubject());
        return bookingService.listMine(userId);
    }

    @PostMapping("/{orderId}/pay")
    public OrderStatusResponse pay(
            @PathVariable long orderId,
            @AuthenticationPrincipal Jwt jwt) {
        long userId = Long.parseLong(jwt.getSubject());
        orderActionService.pay(orderId, userId);
        return new OrderStatusResponse(orderId, "PAID");
    }

    @PostMapping("/{orderId}/cancel")
    public OrderStatusResponse cancel(
            @PathVariable long orderId,
            @AuthenticationPrincipal Jwt jwt) {
        long userId = Long.parseLong(jwt.getSubject());
        orderActionService.cancel(orderId, userId);
        return new OrderStatusResponse(orderId, "CANCELLED");
    }

    public record OrderStatusResponse(long orderId, String status) {}
}