package com.example.ticket_booking.booking;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class BookingOperationService {
    private final BookingOperationMapper mapper;
    private final BookingService bookingService;

    public BookingOperationService(
            BookingOperationMapper mapper,
            BookingService bookingService) {
        this.mapper = mapper;
        this.bookingService = bookingService;
    }

    @Transactional
    public Result book(long eventId, long userId, String operationId) {
        if (eventId <= 0 || userId <= 0
                || operationId == null
                || !operationId.matches("[0-9a-f]{32}")) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "报名参数或操作编号不合法");
        }

        mapper.claim(userId, operationId, eventId);

        BookingOperation operation =
                mapper.findForUpdate(userId, operationId);

        if (operation == null) {
            throw new IllegalStateException("报名操作记录不存在");
        }

        if (operation.getEventId() != eventId) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    "同一操作编号不能更换活动");
        }

        // 已经成功执行过：返回原订单当前的状态。
        if (operation.getOrderId() != null) {
            OrderView order = mapper.findOwnedOrder(
                    operation.getOrderId(), userId, eventId);

            if (order == null) {
                throw new IllegalStateException(
                        "报名操作关联的订单不存在");
            }

            return new Result(
                    operationId,
                    order.getId(),
                    eventId,
                    order.getStatus(),
                    true);
        }

        // 首次执行：复用原来的报名事务。
        long orderId = bookingService.book(eventId, userId);

        if (mapper.attachOrder(userId, operationId, orderId) != 1) {
            throw new IllegalStateException(
                    "保存报名操作结果失败");
        }

        return new Result(
                operationId,
                orderId,
                eventId,
                "UNPAID",
                false);
    }

    public record Result(
            String operationId,
            long orderId,
            long eventId,
            String status,
            boolean replayed) {}
}