package com.example.ticket_booking.booking;

import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Declarables;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OrderExpiryQueueConfig {

    public static final String DELAY_EXCHANGE = "booking.expiry.delay.exchange";
    public static final String DELAY_QUEUE = "booking.expiry.delay.queue";
    public static final String READY_EXCHANGE = "booking.expiry.ready.exchange";
    public static final String READY_QUEUE = "booking.expiry.ready.queue";
    public static final String ROUTING_KEY = "booking.expiry";

    @Bean
    Declarables orderExpiryTopology() {
        DirectExchange delayExchange =
                new DirectExchange(DELAY_EXCHANGE, true, false);
        DirectExchange readyExchange =
                new DirectExchange(READY_EXCHANGE, true, false);

        Queue delayQueue = QueueBuilder.durable(DELAY_QUEUE)
                .ttl(15 * 60 * 1000)
                .deadLetterExchange(READY_EXCHANGE)
                .deadLetterRoutingKey(ROUTING_KEY)
                .build();

        Queue readyQueue = QueueBuilder.durable(READY_QUEUE).build();

        return new Declarables(
                delayExchange,
                readyExchange,
                delayQueue,
                readyQueue,
                BindingBuilder.bind(delayQueue)
                        .to(delayExchange).with(ROUTING_KEY),
                BindingBuilder.bind(readyQueue)
                        .to(readyExchange).with(ROUTING_KEY)
        );
    }
}