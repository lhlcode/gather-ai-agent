package com.example.ticket_booking.event;

import java.time.Duration;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.json.JsonMapper;import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Service
public class EventService {
    private static final Logger log = LoggerFactory.getLogger(EventService.class);

    private static final String CACHE_PREFIX = "ticket:events:published:";
    private static final String NOT_FOUND = "__NOT_FOUND__";
    private static final Duration NOT_FOUND_TTL = Duration.ofSeconds(5);

    // 固定数量的锁，避免为每个活动 ID 永久保存一个锁对象。
    private final Object[] fillLocks = new Object[64];

    private final EventMapper eventMapper;
    private final StringRedisTemplate redisTemplate;
    private final JsonMapper jsonMapper;

    public EventService(
            EventMapper eventMapper,
            StringRedisTemplate redisTemplate,
            JsonMapper jsonMapper) {
        this.eventMapper = eventMapper;
        this.redisTemplate = redisTemplate;
        this.jsonMapper = jsonMapper;

        for (int i = 0; i < fillLocks.length; i++) {
            fillLocks[i] = new Object();
        }
    }

    public List<EventSummary> listPublished() {
        return eventMapper.findPublished();
    }

    public EventSummary findPublishedById(long eventId) {
        String key = cacheKey(eventId);

        // 大部分请求在这里命中，不需要进入锁。
        try {
            String value = redisTemplate.opsForValue().get(key);
            if (value != null) {
                return decode(value);
            }
        } catch (DataAccessException e) {
            log.warn("读取 Redis 失败，改查 MySQL，活动 ID：{}", eventId, e);
            return loadFromDatabase(eventId);
        } catch (JacksonException e) {
            log.warn("活动详情缓存内容无效，准备重新加载，活动 ID：{}", eventId, e);
        }

        synchronized (lockFor(eventId)) {
            // 等待锁期间，前一个请求可能已经填好了缓存，必须再查一次。
            try {
                String value = redisTemplate.opsForValue().get(key);
                if (value != null) {
                    return decode(value);
                }
            } catch (DataAccessException e) {
                log.warn("再次读取 Redis 失败，改查 MySQL，活动 ID：{}", eventId, e);
                return loadFromDatabase(eventId);
            } catch (JacksonException e) {
                log.warn("活动详情缓存内容仍无效，改查 MySQL，活动 ID：{}", eventId, e);
            }

            EventSummary event = loadFromDatabase(eventId);

            try {
                if (event == null) {
                    redisTemplate.opsForValue().set(key, NOT_FOUND, NOT_FOUND_TTL);
                } else {
                    String json = jsonMapper.writeValueAsString(event);
                    // 最长仍为 10 秒，不增加原先的最大陈旧时间。
                    int seconds = ThreadLocalRandom.current().nextInt(5, 11);
                    redisTemplate.opsForValue().set(
                            key, json, Duration.ofSeconds(seconds));
                }
            } catch (DataAccessException | JacksonException e) {
                log.warn("写入活动详情缓存失败，活动 ID：{}", eventId, e);
            }

            return event;
        }
    }

    public void evictPublishedDetail(long eventId) {
        // 发布活动时删除可能存在的“查无此活动”缓存。
        synchronized (lockFor(eventId)) {
            try {
                redisTemplate.delete(cacheKey(eventId));
            } catch (DataAccessException e) {
                log.warn("删除活动详情缓存失败，活动 ID：{}", eventId, e);
            }
        }
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void evictAfterQuotaChanged(EventQuotaChangedEvent event) {
        evictPublishedDetail(event.eventId());
    }
    private EventSummary decode(String value) throws JacksonException {
        if (NOT_FOUND.equals(value)) {
            return null;
        }
        return jsonMapper.readValue(value, EventSummary.class);
    }

    private EventSummary loadFromDatabase(long eventId) {
        log.info("活动详情回源 MySQL，活动 ID：{}", eventId);
        return eventMapper.findPublishedById(eventId);
    }

    private Object lockFor(long eventId) {
        int index = Math.floorMod(Long.hashCode(eventId), fillLocks.length);
        return fillLocks[index];
    }

    private String cacheKey(long eventId) {
        return CACHE_PREFIX + eventId;
    }
}