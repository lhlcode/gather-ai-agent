package com.example.ticket_booking.booking;
import com.example.ticket_booking.event.EventQuotaChangedEvent;
import org.springframework.context.ApplicationEventPublisher;
import com.example.ticket_booking.event.EventMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class OrderActionService {
    private final BookingOrderMapper orderMapper;
    private final EventMapper eventMapper;
    private final ApplicationEventPublisher eventPublisher;

    public OrderActionService(
            BookingOrderMapper orderMapper,
            EventMapper eventMapper,
            ApplicationEventPublisher eventPublisher) {
        this.orderMapper = orderMapper;
        this.eventMapper = eventMapper;
        this.eventPublisher = eventPublisher;
    }

    @Transactional
    public void pay(long orderId, long userId) {
        if (orderMapper.findEventIdForUser(orderId, userId) == null) {
            throw new OrderNotFoundException();
        }

        if (orderMapper.markPaidIfValid(orderId, userId) != 1) {
            throw new OrderStateConflictException("订单不能支付：状态已变化或支付时间已过");
        }
    }

    @Transactional
    public void cancel(long orderId, long userId) {
        Long eventId = orderMapper.findEventIdForUser(orderId, userId);
        if (eventId == null) {
            throw new OrderNotFoundException();
        }

        // 和过期关单保持同一加锁顺序：先活动，后订单。
        if (eventMapper.lockById(eventId) == null) {
            throw new IllegalStateException("订单关联的活动不存在");
        }

        if (orderMapper.markCancelledIfUnpaid(orderId, userId) != 1) {
            throw new OrderStateConflictException("只有待支付订单可以取消");
        }

        if (eventMapper.releaseOne(eventId) != 1) {
            throw new IllegalStateException("归还活动名额失败");
        }
        eventPublisher.publishEvent(new EventQuotaChangedEvent(eventId));
    }
}