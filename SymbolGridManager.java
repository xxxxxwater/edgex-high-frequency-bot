package com.tradez.order.common.strategy.py38;

import org.springframework.data.redis.core.RedisCallback;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

// ===== 交易对网格管理器 =====
public class SymbolGridManager {
    public final StringRedisTemplate redisTemplate;
    public final String contractId;
    public final String thirdAccountId;
    public GridStrategyConfig config;

    // Redis Key 定义 (格式: grid:strategy:{accountId}:{contractId}:{suffix})
    private static final String KEY_PREFIX = "grid:strategy:";
    private static final String KEY_PENDING_ORDERS = ":pending_orders"; // Hash: OrderId -> GridLevel JSON
    private static final String KEY_BUY_GRIDS = ":buy_grids";         // List/String: GridLevel JSON List
    private static final String KEY_SELL_GRIDS = ":sell_grids";       // List/String: GridLevel JSON List
    private static final String KEY_NET_POSITION = ":net_pos";          // String: BigDecimal 净持仓
    private static final String KEY_POS_COUNT_LONG = ":pos:long_count"; // String: Integer 多头计数
    private static final String KEY_POS_COUNT_SHORT = ":pos:short_count"; // String: Integer 空头计数
    private static final String KEY_LAST_ORDER_TIME = ":last_order_time"; // String: Long

    // 用于构造函数初始化（需要外部在 executeStrategy 中创建）
    public SymbolGridManager(StringRedisTemplate redisTemplate, String contractId, String thirdAccountId, GridStrategyConfig config) {
        this.redisTemplate = redisTemplate;
        this.contractId = contractId;
        this.thirdAccountId = thirdAccountId;
        this.config = config;
    }


    // --- Key 生成 ---
    private String getKey(String suffix) {
        return KEY_PREFIX + thirdAccountId + ":" + contractId + suffix;
    }

    // --- 状态操作：订单时间 ---
    public long getLastOrderTime() {
        String timeStr = redisTemplate.opsForValue().get(getKey(KEY_LAST_ORDER_TIME));
        return timeStr != null ? Long.parseLong(timeStr) : 0;
    }

    public void updateOrderTime() {
        redisTemplate.opsForValue().set(getKey(KEY_LAST_ORDER_TIME), String.valueOf(System.currentTimeMillis() / 1000));
    }

    // --- 状态操作：下单限制检查 (基于 Redis) ---
    public boolean canPlaceOrder() {
        long now = System.currentTimeMillis() / 1000;
        long lastOrderTime = getLastOrderTime();
        if (now - lastOrderTime < GridStrategyConfig.minOrderInterval) { // 使用 GridStrategyConfig 的 getter
            return false;
        }

        // 检查最大挂单数限制
        Long pendingCount = redisTemplate.opsForHash().size(getKey(KEY_PENDING_ORDERS));
        return pendingCount < GridStrategyConfig.maxOpenOrders; // 使用 GridStrategyConfig 的 getter
    }

    // --- 状态操作：持仓计数和净持仓 ---

    /**
     * 获取多头头寸计数
     */
    public int getLongPositionCount() {
        String countStr = redisTemplate.opsForValue().get(getKey(KEY_POS_COUNT_LONG));
        return countStr != null ? Integer.parseInt(countStr) : 0;
    }

    /**
     * 获取空头头寸计数
     */
    public int getShortPositionCount() {
        String countStr = redisTemplate.opsForValue().get(getKey(KEY_POS_COUNT_SHORT));
        return countStr != null ? Integer.parseInt(countStr) : 0;
    }

    /**
     * 检查是否可以开仓
     */
    public boolean canOpenPosition(GridStrategyConfig.OrderSide side) {
        if (side == GridStrategyConfig.OrderSide.BUY) {
            return getLongPositionCount() < GridStrategyConfig.maxPositionPerSide;
        } else {
            return getShortPositionCount() < GridStrategyConfig.maxPositionPerSide;
        }
    }

    /**
     * 更新持仓（净持仓和计数） - **使用 Redis 事务保证原子性**
     * 修复：平仓时正确处理净持仓，确保持仓计数和净持仓一致
     */
    public void updatePosition(GridStrategyConfig.OrderSide side, BigDecimal quantity, boolean isOpen) {
        String netPosKey = getKey(KEY_NET_POSITION);
        String countLongKey = getKey(KEY_POS_COUNT_LONG);
        String countShortKey = getKey(KEY_POS_COUNT_SHORT);

        redisTemplate.execute((RedisCallback<List<Object>>) connection -> {
            connection.openPipeline();

            // 1. 获取当前状态
            byte[] netPosKeyBytes = netPosKey.getBytes();
            byte[] countLongKeyBytes = countLongKey.getBytes();
            byte[] countShortKeyBytes = countShortKey.getBytes();

            connection.get(netPosKeyBytes);
            connection.get(countLongKeyBytes);
            connection.get(countShortKeyBytes);

            List<Object> results = connection.closePipeline();

            String currentNetPosStr = (results.get(0) != null) ? new String((byte[]) results.get(0)) : null;
            String currentLongCountStr = (results.get(1) != null) ? new String((byte[]) results.get(1)) : null;
            String currentShortCountStr = (results.get(2) != null) ? new String((byte[]) results.get(2)) : null;

            BigDecimal netPos = (currentNetPosStr != null) ? new BigDecimal(currentNetPosStr) : BigDecimal.ZERO;
            int longCount = (currentLongCountStr != null) ? Integer.parseInt(currentLongCountStr) : 0;
            int shortCount = (currentShortCountStr != null) ? Integer.parseInt(currentShortCountStr) : 0;

            // 2. 计算新状态
            BigDecimal newNetPos = netPos;
            int newLongCount = longCount;
            int newShortCount = shortCount;

            if (isOpen) {
                // 开仓：增加持仓
                if (side == GridStrategyConfig.OrderSide.BUY) { // 开多
                    newNetPos = netPos.add(quantity);
                    newLongCount = longCount + 1;
                } else { // 开空
                    newNetPos = netPos.subtract(quantity);
                    newShortCount = shortCount + 1;
                }
            } else { 
                // 平仓：减少持仓（修复：平仓时净持仓应该向0靠拢）
                if (side == GridStrategyConfig.OrderSide.SELL) { // 平多（卖出）
                    newNetPos = netPos.subtract(quantity);
                    newLongCount = Math.max(0, longCount - 1);
                } else { // 平空（买入）
                    newNetPos = netPos.add(quantity);
                    newShortCount = Math.max(0, shortCount - 1);
                }
            }

            // 3. 写入新状态
            connection.set(netPosKeyBytes, newNetPos.toPlainString().getBytes());
            connection.set(countLongKeyBytes, String.valueOf(newLongCount).getBytes());
            connection.set(countShortKeyBytes, String.valueOf(newShortCount).getBytes());

            return null;
        });
    }

    // --- 网格订单操作：Pending Hash ---

    /** 从 Redis 获取所有待处理订单 */
    public Map<String, GridStrategyConfig.GridLevel> getAllPendingOrders() {
        String key = getKey(KEY_PENDING_ORDERS);
        Map<Object, Object> entries = redisTemplate.opsForHash().entries(key);

        return entries.entrySet().stream()
                .collect(Collectors.toMap(
                        e -> (String) e.getKey(),
                        e -> JsonUtil.fromJson((String) e.getValue(), GridStrategyConfig.GridLevel.class)
                ));
    }

    /** 向 Redis 增加一个待处理订单 */
    public void addPendingOrder(String orderId, GridStrategyConfig.GridLevel gridLevel) {
        String key = getKey(KEY_PENDING_ORDERS);
        String jsonValue = JsonUtil.toJson(gridLevel);
        redisTemplate.opsForHash().put(key, orderId, jsonValue);
    }

    /** 从 Redis 移除一个待处理订单 */
    public void removePendingOrder(String orderId) {
        String key = getKey(KEY_PENDING_ORDERS);
        redisTemplate.opsForHash().delete(key, orderId);
    }

    // --- 网格列表操作：Buy/Sell Lists (用 List 存储 JSON 字符串) ---

    /** 清空并设置新的买单网格列表 */
    public void setBuyGrids(List<GridStrategyConfig.GridLevel> grids) {
        String key = getKey(KEY_BUY_GRIDS);
        redisTemplate.delete(key);
        if (!grids.isEmpty()) {
            List<String> jsonList = grids.stream().map(JsonUtil::toJson).collect(Collectors.toList());
            redisTemplate.opsForList().rightPushAll(key, jsonList);
        }
    }

    /** 清空并设置新的卖单网格列表 */
    public void setSellGrids(List<GridStrategyConfig.GridLevel> grids) {
        String key = getKey(KEY_SELL_GRIDS);
        redisTemplate.delete(key);
        if (!grids.isEmpty()) {
            List<String> jsonList = grids.stream().map(JsonUtil::toJson).collect(Collectors.toList());
            redisTemplate.opsForList().rightPushAll(key, jsonList);
        }
    }

}

