package com.tradez.order.common.strategy.py38;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

public class JsonUtil {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static String toJson(Object obj) {
        try {
            return MAPPER.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            // 生产环境应记录日志并抛出业务异常
            throw new RuntimeException("序列化失败", e);
        }
    }

    public static <T> T fromJson(String json, Class<T> clazz) {
        try {
            return MAPPER.readValue(json, clazz);
        } catch (JsonProcessingException e) {
            // 生产环境应记录日志并抛出业务异常
            throw new RuntimeException("反序列化失败", e);
        }
    }
}
