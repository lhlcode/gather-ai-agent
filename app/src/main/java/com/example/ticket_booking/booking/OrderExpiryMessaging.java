package com.example.ticket_booking.booking;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
public class OrderExpiryMessaging {

    private static final Logger log =
            LoggerFactory.getLogger(OrderExpiryMessaging.class);

    private final RabbitTemplate rabbitTemplate;
    private final OrderExpiryService expiryService;

    public OrderExpiryMessaging(
            RabbitTemplate rabbitTemplate,
            OrderExpiryService expiryService) {
        this.rabbitTemplate = rabbitTemplate;
        this.expiryService = expiryService;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void publishAfterBookingCommitted(BookingCreatedEvent event) {
        try {
            rabbitTemplate.convertAndSend(
                    OrderExpiryQueueConfig.DELAY_EXCHANGE,
                    OrderExpiryQueueConfig.ROUTING_KEY,
                    Long.toString(event.orderId())
            );
            log.info("订单 {} 的过期检查消息已发送", event.orderId());
        } catch (RuntimeException e) {
            // 订单已经提交；发消息失败不能把成功报名误报为失败。
            // 原有的定时扫描会继续处理过期订单。
            log.error("订单 {} 的过期消息发送失败，等待定时扫描兜底",
                    event.orderId(), e);
        }
    }

    @RabbitListener(queues = OrderExpiryQueueConfig.READY_QUEUE)
    public void checkExpiredOrder(String orderIdText) {
        try {
            long orderId = Long.parseLong(orderIdText);
            if (expiryService.expireOne(orderId)) {
                log.info("消息触发订单 {} 过期，名额已归还", orderId);
            }
        } catch (RuntimeException e) {
            // 消息处理失败时，数据库扫描仍会重试真实的过期订单。
            log.error("处理过期检查消息 {} 失败", orderIdText, e);
        }
    }
}