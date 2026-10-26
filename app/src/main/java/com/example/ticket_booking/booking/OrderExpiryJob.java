package com.example.ticket_booking.booking;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class OrderExpiryJob {
    private static final Logger log =
            LoggerFactory.getLogger(OrderExpiryJob.class);

    private final BookingOrderMapper orderMapper;
    private final OrderExpiryService expiryService;

    public OrderExpiryJob(
            BookingOrderMapper orderMapper,
            OrderExpiryService expiryService) {
        this.orderMapper = orderMapper;
        this.expiryService = expiryService;
    }

    @Scheduled(initialDelay = 5000, fixedDelay = 60000)
    public void closeExpiredOrders() {
        for (Long orderId : orderMapper.findExpiredUnpaidIds()) {
            try {
                if (expiryService.expireOne(orderId)) {
                    log.info("订单 {} 已过期，名额已归还", orderId);
                }
            } catch (RuntimeException e) {
                log.error("处理过期订单 {} 失败，下轮重试", orderId, e);
            }
        }
    }
}