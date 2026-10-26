package com.example.ticket_booking.booking;

import com.example.ticket_booking.event.EventMapper;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;import java.util.List;import org.springframework.context.ApplicationEventPublisher;import com.example.ticket_booking.event.EventQuotaChangedEvent;

@Service
public class BookingService {
    private final ApplicationEventPublisher eventPublisher;
    private final EventMapper eventMapper;
    private final BookingOrderMapper orderMapper;

    public BookingService(
            EventMapper eventMapper,
            BookingOrderMapper orderMapper,
            ApplicationEventPublisher eventPublisher) {
        this.eventMapper = eventMapper;
        this.orderMapper = orderMapper;
        this.eventPublisher = eventPublisher;
    }
    public List<OrderView> listMine(long userId) {
        return orderMapper.findByUserId(userId);
    }

    @Transactional
    public long book(long eventId, long userId) {
        if (eventMapper.reserveOne(eventId) != 1) {
            throw new BookingUnavailableException();
        }

        BookingOrder order = new BookingOrder(eventId, userId);
        try {
            if (orderMapper.insert(order) != 1 || order.getId() == null) {
                throw new IllegalStateException("订单创建失败");
            }
        } catch (DuplicateKeyException e) {
            throw new ActiveBookingExistsException();
        }
        eventPublisher.publishEvent(new BookingCreatedEvent(order.getId()));
        eventPublisher.publishEvent(new EventQuotaChangedEvent(eventId));
        return order.getId();
    }
}