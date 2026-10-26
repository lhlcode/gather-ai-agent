package com.example.ticket_booking.booking;

import com.example.ticket_booking.event.EventMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;import com.example.ticket_booking.event.EventQuotaChangedEvent;
import org.springframework.context.ApplicationEventPublisher;

@Service
public class OrderExpiryService {//用户某一个订单过期，返回名额操作
    private final BookingOrderMapper orderMapper;
    private final EventMapper eventMapper;
    private final ApplicationEventPublisher eventPublisher;

    public OrderExpiryService(
            BookingOrderMapper orderMapper,
            EventMapper eventMapper,
            ApplicationEventPublisher eventPublisher) {
        this.orderMapper = orderMapper;
        this.eventMapper = eventMapper;
        this.eventPublisher = eventPublisher;
    }
    @Transactional
    public boolean expireOne(long orderId) {
        Long eventId = orderMapper.findEventId(orderId);
        if (eventId == null) {
            return false;
        }

        if (eventMapper.lockById(eventId) == null) {
            throw new IllegalStateException("订单关联的活动不存在");
        }

        if (orderMapper.markExpiredIfOverdue(orderId) != 1) {
            return false;
        }

        if (eventMapper.releaseOne(eventId) != 1) {
            throw new IllegalStateException("归还活动名额失败");
        }
        eventPublisher.publishEvent(new EventQuotaChangedEvent(eventId));
        return true;
    }
}