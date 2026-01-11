package com.tradez.order.common.strategy.py38;


import com.tradez.common.util.BigDecimalUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

@Slf4j
@Component
public class HighFrequencyMarketMakingStrategyV38Service {

    @Resource
    EdgeXClient edgeXClient;

    @Resource
    StringRedisTemplate stringRedisTemplate;

    public void executeStrategy(List<String> thirdAccountIds, List<String> contractIdList, Map<String, SymbolGridManager> symbolGridManagerMap) {
        //检查风险控制
        for (String contractId : contractIdList) {
            try {
                SymbolGridManager localGridMgr = symbolGridManagerMap.get(contractId);
                if (localGridMgr == null) {
                    log.error("获取网格管理器配置失败");
                    continue;
                }
                GridStrategyConfig config = localGridMgr.config;
                // 所有账户
                for (String thirdAccountId : thirdAccountIds) {
                    try {
                        SymbolGridManager gridMgr = new SymbolGridManager(stringRedisTemplate, contractId, thirdAccountId, config);
                        // API调用间隔保护，避免请求过于频繁
                        sleepApiInterval();
                        // 获取订单簿数据，深度为15档
                        GridStrategyConfig.OrderBook orderBook = edgeXClient.getOrderBook(contractId, GridStrategyConfig.depth);
                        if (orderBook == null) {
                            log.error("获取订单簿数据失败");
                            continue;
                        }
                        // 计算中间价格（买一和卖一的平均价）
                        BigDecimal midPrice = orderBook.getMidPrice();
                        if (midPrice.compareTo(BigDecimal.ZERO) <= 0) {
                            log.error("中间价格异常:{},{}", contractId, midPrice);
                            continue;
                        }

                        // 更新网格管理器中的价格信息
                        BigDecimal lastMidPrice = midPrice;
                        long lastUpdateTime = System.currentTimeMillis() / 1000;

                        // 检查是否需要刷新网格（价格变动较大时需要重新布网）
                        boolean shouldRefresh = shouldRefreshGrid(thirdAccountId, contractId, gridMgr, midPrice);

                        if (shouldRefresh) {
                            // 只取消开仓单，保留平仓单保护已有持仓
                            sleepApiInterval();
                            cancelOpenOrders(gridMgr, thirdAccountId, contractId);

                            // 根据最新价格重新生成网格订单
                            sleepApiInterval();
                            generateGridOrders(thirdAccountId, gridMgr, contractId, midPrice, orderBook);

                            // 存储到Redis缓存
                            String symbolKey = "grid:last_mid_price:" + contractId;
                            stringRedisTemplate.opsForValue().set(symbolKey, BigDecimalUtil.bigDecimalToStr(lastMidPrice));
                            stringRedisTemplate.opsForValue().set(symbolKey + ":last_update_time", String.valueOf(lastUpdateTime));

                        }
                        // 检查订单成交情况并处理
                        sleepApiInterval();
                        checkFills(gridMgr, thirdAccountId, contractId);
                    } catch (Exception e) {
                        log.error("执行策略异常", e);
                    }
                }
            } catch (Exception e) {
                log.error("执行策略异常", e);
            }
        }

    }


    /**
     * 只取消开仓单，保留平仓单
     * 避免刷新网格时取消平仓单导致持仓暴露
     */
    private void cancelOpenOrders(SymbolGridManager gridMgr, String thirdAccountId, String contractId) {
        try {
            // 获取所有待处理订单
            Map<String, GridStrategyConfig.GridLevel> pendingOrders = gridMgr.getAllPendingOrders();

            for (Map.Entry<String, GridStrategyConfig.GridLevel> entry : pendingOrders.entrySet()) {
                String orderId = entry.getKey();
                GridStrategyConfig.GridLevel gridLevel = entry.getValue();

                // 只取消开仓单（isCloseOrder = false）
                if (!gridLevel.isCloseOrder) {
                    edgeXClient.cancelOrder(thirdAccountId, contractId, orderId);
                    gridMgr.removePendingOrder(orderId);
                    log.info("{} 取消开仓单: {} {} @ {}", contractId, gridLevel.side, gridLevel.size, gridLevel.price);
                    sleepApiInterval();
                }
            }
        } catch (Exception e) {
            log.error("{} 取消开仓单失败: {}", contractId, e.getMessage(), e);
        }
    }

    /**
     * 检查网格是否需要刷新
     *
     * @param contractId
     * @return
     */
    private boolean shouldRefreshGrid(String thirdAccountId, String contractId, SymbolGridManager gridMgr, BigDecimal currentPrice) {
        // 如果没有待成交的订单（不包括平仓单），就应该生成新网格
        int pendingOrdersCount = edgeXClient.pendingOrders(thirdAccountId, contractId);
        log.info("合约: {} 用户: {} 待成交的订单: {},没有未成交订单，网格生成", contractId, thirdAccountId,pendingOrdersCount);
        if (pendingOrdersCount == 0) {
            log.info("合约: {} 用户: {} ,没有未成交订单，网格生成", contractId, thirdAccountId);
            return true;
        }

        String symbolKey = "grid:last_mid_price:" + contractId;
        String priceStr = stringRedisTemplate.opsForValue().get(symbolKey);
        String timeStr = stringRedisTemplate.opsForValue().get(symbolKey + ":last_update_time");

        // 首次运行，Redis中没有数据
        if (priceStr == null || timeStr == null) {
            log.info("{},{} 首次运行，需要生成网格", thirdAccountId, contractId);
            return true;
        }

        try {
            BigDecimal last_mid_price = new BigDecimal(priceStr);
            long last_update_time = Long.parseLong(timeStr);

            // 价格偏离过大
            if (last_mid_price.compareTo(BigDecimal.ZERO) > 0) {
                BigDecimal priceDeviation = currentPrice.subtract(last_mid_price)
                        .abs()
                        .divide(last_mid_price, 8, RoundingMode.HALF_UP);
                if (priceDeviation.compareTo(new BigDecimal("0.005")) > 0) { // 偏离0.5%
                    log.info("{},{} 价格偏离过大: {}%, 需要刷新网格", thirdAccountId, contractId, priceDeviation.multiply(new BigDecimal("100")));
                    return true;
                }
            }

            // 定期刷新
            long now = System.currentTimeMillis() / 1000;
            if (now - last_update_time > GridStrategyConfig.orderRefreshInterval) {
                log.info("{},{} 超过刷新间隔: {}秒, 需要刷新网格", thirdAccountId, contractId, (now - last_update_time));
                return true;
            }
        } catch (Exception e) {
            log.error("{},{} 检查刷新条件异常: {}", thirdAccountId, contractId, e.getMessage(), e);
            return false;
        }
        log.info("{},{} 不需要刷新网格", thirdAccountId, contractId);
        return false;
    }


    /**
     * 生成网格订单
     *
     * @param contractId
     * @param midPrice
     * @param orderBook
     */
    private void generateGridOrders(String thirdAccountId, SymbolGridManager gridMgr, String contractId, BigDecimal midPrice, GridStrategyConfig.OrderBook orderBook) {
        try {
            // 风险检查：检查当前持仓是否超限
            int longCount = gridMgr.getLongPositionCount();
            int shortCount = gridMgr.getShortPositionCount();
            int totalPositions = longCount + shortCount;

            if (totalPositions >= GridStrategyConfig.maxPositionPerSide * 2) {
                log.info("{},{} 持仓已达上限: 多头={}, 空头={}, 跳过网格生成", thirdAccountId, contractId, longCount, shortCount);
                return;
            }

            // 清空旧网格 (Redis List 操作)
            List<GridStrategyConfig.GridLevel> newBuyGrids = new ArrayList<>();
            List<GridStrategyConfig.GridLevel> newSellGrids = new ArrayList<>();
            // 在生成之前先清空 Redis 中的 List
            gridMgr.setBuyGrids(Collections.emptyList());
            gridMgr.setSellGrids(Collections.emptyList());

            BigDecimal currentBalance = edgeXClient.getBalance(thirdAccountId, contractId);

            // 检查可用余额
            if (currentBalance.compareTo(BigDecimal.ZERO) <= 0) {
                log.info("合约: {} 用户: {} ,余额不足，跳过网格生成", contractId, thirdAccountId);
                return;
            }

            // 计算订单大小（使用可用余额）
            BigDecimal minSize = GridStrategyConfig.getMinOrderSize(contractId);
            BigDecimal orderValue = currentBalance.multiply(GridStrategyConfig.positionSizePct);
            BigDecimal baseSize = orderValue.divide(midPrice, 8, RoundingMode.HALF_UP);

            // 确保满足最小订单量
            if (baseSize.compareTo(minSize) < 0) {
                baseSize = minSize;
            }


            // 获取盘口价格
            GridStrategyConfig.OrderBook.Level bestBid = orderBook.getBestBid();
            GridStrategyConfig.OrderBook.Level bestAsk = orderBook.getBestAsk();

            if (bestBid == null || bestAsk == null) {
                log.info("合约: {} 用户: {} ,盘口数据为空，跳过网格生成", contractId, thirdAccountId);
                return;
            }

            BigDecimal bestBidPrice = bestBid.getPrice();
            BigDecimal bestAskPrice = bestAsk.getPrice();

            // 生成买单网格（低于最佳买价）
            for (int i = 0; i < GridStrategyConfig.gridLevels; i++) {
                if (!gridMgr.canPlaceOrder()) {
                    log.info("合约: {} 用户: {} ,无法继续生成买单，跳过 (时间或数量限制)", contractId, thirdAccountId);
                    break;
                }
                if (!gridMgr.canOpenPosition(GridStrategyConfig.OrderSide.BUY)) {
                    log.info("合约: {} 用户: {} ,无法继续生成买单，跳过 (多头持仓已满: {})", contractId, thirdAccountId, gridMgr.getLongPositionCount());
                    break;
                }

                // 计算网格价格（略低于盘口）
                BigDecimal offset = GridStrategyConfig.gridSpacingPct.multiply(BigDecimal.valueOf(i + 1));
                BigDecimal gridPrice = bestBidPrice.multiply(BigDecimal.ONE.subtract(offset));

                // 创建网格层级
                GridStrategyConfig.GridLevel gridLevel = new GridStrategyConfig.GridLevel(gridPrice, baseSize, GridStrategyConfig.OrderSide.BUY);

                // 下单
                GridStrategyConfig.Order order = new GridStrategyConfig.Order(
                        thirdAccountId,
                        contractId,
                        GridStrategyConfig.OrderSide.BUY,
                        GridStrategyConfig.OrderType.LIMIT,
                        baseSize,
                        gridPrice,
                        GridStrategyConfig.leverage
                );

                String orderId = edgeXClient.placeOrder(order);
                if (orderId != null) {
                    gridLevel.setOrderId(orderId);
                    gridMgr.addPendingOrder(orderId, gridLevel); // <-- 修正：Redis Hash 操作
                    newBuyGrids.add(gridLevel); // 收集到本地 List
                    gridMgr.updateOrderTime(); // Redis Time 操作
                    log.info("{},{},{} 挂买单: {} x {}", thirdAccountId, contractId, orderId, gridPrice, baseSize);
                }

                // API限速保护
//                sleepApiInterval();


                // 生成卖单网格（高于最佳卖价）

                // 计算网格价格（略高于盘口）
                BigDecimal offsetSell = GridStrategyConfig.gridSpacingPct.multiply(BigDecimal.valueOf(i + 1));
                BigDecimal gridPriceSell = bestAskPrice.multiply(BigDecimal.ONE.add(offsetSell));

                // 创建网格层级
                GridStrategyConfig.GridLevel gridSellLevel = new GridStrategyConfig.GridLevel(gridPriceSell, baseSize, GridStrategyConfig.OrderSide.SELL);

                // 下单
                GridStrategyConfig.Order orderSell = new GridStrategyConfig.Order(
                        thirdAccountId,
                        contractId,
                        GridStrategyConfig.OrderSide.SELL,
                        GridStrategyConfig.OrderType.LIMIT,
                        baseSize,
                        gridPriceSell,
                        GridStrategyConfig.leverage
                );

                String orderSellId = edgeXClient.placeOrder(orderSell);
                if (orderSellId != null) {
                    gridSellLevel.setOrderId(orderSellId);
                    gridMgr.addPendingOrder(orderSellId, gridSellLevel); // <-- 修正：Redis Hash 操作
                    newSellGrids.add(gridSellLevel); // 收集到本地 List
                    gridMgr.updateOrderTime(); // Redis Time 操作
                    log.info("{},{},{} 挂卖单: {} x {}", thirdAccountId, contractId, orderSellId, gridPriceSell, baseSize);
                }

            }

            // 生成卖单网格（高于最佳卖价）
//            for (int i = 0; i < GridStrategyConfig.gridLevels; i++) {
//                    long timeSinceLastOrder = System.currentTimeMillis() / 1000 - gridMgr.getLastOrderTime();
//                if (!gridMgr.canPlaceOrder()) {
//                    log.info("合约: {} 用户: {} ,无法继续生成卖单，跳过 (时间或数量限制: 距上次下单={}秒, 最小间隔要求={}秒)",
//                            contractId, thirdAccountId,
//                            timeSinceLastOrder,
//                            GridStrategyConfig.minOrderInterval);
//                    break;
//                }


//                if (!gridMgr.canOpenPosition(GridStrategyConfig.OrderSide.SELL)) {
//                    log.info("合约: {} 用户: {} ,无法继续生成卖单，跳过 (空头持仓已满: {}/{})",
//                            contractId, thirdAccountId,
//                            gridMgr.getShortPositionCount(),
//                            GridStrategyConfig.maxPositionPerSide);
//                    break;
//                }


//            }

            // 统一写入 Redis List
            gridMgr.setBuyGrids(newBuyGrids);
            gridMgr.setSellGrids(newSellGrids);
            log.info("{},{} 网格生成: {}买 + {}卖", thirdAccountId, contractId, newBuyGrids.size(), newSellGrids.size());
        } catch (Exception e) {
            log.error("{},{} 生成网格订单失败: {}", thirdAccountId, contractId, e.getMessage(), e);
        }
    }

    /**
     * 检查订单成交情况并处理
     *
     * @param gridMgr        Redis 状态管理器
     * @param thirdAccountId 账户ID
     * @param contractId     交易对
     */
    private void checkFills(SymbolGridManager gridMgr, String thirdAccountId, String contractId) {
        try {
            if (gridMgr == null) {
                return;
            }
            log.info("{}, {} 开始检查订单成交情况", thirdAccountId, contractId);

            // 1. 从 Redis 获取所有本地追踪的待处理订单
            Map<String, GridStrategyConfig.GridLevel> pendingOrdersRedis = gridMgr.getAllPendingOrders();

            // 获取活跃订单
            List<String> activeOrders = edgeXClient.getActiveOrderPage(thirdAccountId, contractId);
            Set<String> activeOrderIds = new HashSet<>();
            if (activeOrders != null) {
                for (String orderId : activeOrders) {
                    if (orderId != null) {
                        activeOrderIds.add(orderId);
                    }
                }
            }

            // 检查哪些订单已成交 (基于 Redis 数据)
            List<Map.Entry<String, GridStrategyConfig.GridLevel>> filledOrders = new ArrayList<>();
            for (Map.Entry<String, GridStrategyConfig.GridLevel> entry : pendingOrdersRedis.entrySet()) {
                String orderId = entry.getKey();
                GridStrategyConfig.GridLevel gridLevel = entry.getValue();

                if (!activeOrderIds.contains(orderId)) {
                    // 订单不在活跃列表，可能已成交或取消
                    // 注意：这里无法区分成交和取消，建议后续调用交易所API确认
                    filledOrders.add(new AbstractMap.SimpleEntry<>(orderId, gridLevel));
                    log.info("{},{} 订单不在活跃列表: {} {} @ {} ({})",
                            thirdAccountId, contractId, gridLevel.side, gridLevel.size, gridLevel.price,
                            gridLevel.isCloseOrder ? "平仓单" : "开仓单");
                }
            }
            log.info("{} 检测到 {} 个订单状态变化", contractId, filledOrders.size());
            if (filledOrders.isEmpty()) {
                return; // 没有成交订单，直接返回
            }

            // 处理成交订单
            for (Map.Entry<String, GridStrategyConfig.GridLevel> entry : filledOrders) {
                log.info("{},{} 订单成交: {}", thirdAccountId, contractId, entry);
                String orderId = entry.getKey();
                GridStrategyConfig.GridLevel gridLevel = entry.getValue();

                // 标记为成交
                gridLevel.setFilled(true);
                gridLevel.setFilledTime(System.currentTimeMillis() / 1000);

                // 更新持仓（区分开仓和平仓）
                if (gridLevel.isCloseOrder) {
                    // 平仓单：减少持仓计数
                    gridMgr.updatePosition(gridLevel.getSide(), gridLevel.getSize(), false); // <-- 修正：Redis
                    log.info("{},{} 平仓成交: {} {} @ {}", thirdAccountId, contractId, gridLevel.getSide(), gridLevel.getSize(), gridLevel.getPrice());
                } else {
                    // 开仓单：增加持仓计数
                    gridMgr.updatePosition(gridLevel.getSide(), gridLevel.getSize(), true); // <-- 修正：Redis
                    log.info("{},{} 订单成交: {} {} @ {}", thirdAccountId, contractId, gridLevel.getSide(), gridLevel.getSize(), gridLevel.getPrice()); // symbol 修正为 contractId
                    // 立即在相反方向挂平仓单
                    placeCloseOrder(gridMgr, thirdAccountId, contractId, gridLevel); // <-- 修正签名
                }
                // 移除待处理订单 (Redis Hash 操作)
                gridMgr.removePendingOrder(orderId); // <-- 修正：Redis
            }
        } catch (Exception e) {
            log.error("{} 检查成交失败: {}", contractId, e.getMessage(), e);
        }
    }


    /**
     * 根据 Python 逻辑，在相反方向挂平仓单
     * 逻辑: 平仓价 = 开仓价 * (1 ± grid_spacing_pct * 1.5)
     *
     * @param gridMgr         Redis 状态管理器
     * @param thirdAccountId  账户ID
     * @param contractId      交易对
     * @param filledGridLevel 刚刚成交的开仓网格层级
     */
    private void placeCloseOrder(SymbolGridManager gridMgr, String thirdAccountId, String contractId, GridStrategyConfig.GridLevel filledGridLevel) {
        log.info("{}, {} 尝试在相反方向挂平仓单: {} @ {}", thirdAccountId, contractId, filledGridLevel.getSide(), filledGridLevel.getPrice());
        try {
            // 1. 计算利润偏移量 (profit_offset = grid_spacing_pct * 1.5)
            // Python: profit_offset = self.strategy_config.grid_spacing_pct * Decimal("1.5")
            final BigDecimal PROFIT_FACTOR = new BigDecimal("1.5");
            final BigDecimal profitOffset = GridStrategyConfig.gridSpacingPct.multiply(PROFIT_FACTOR);

            final BigDecimal ONE = BigDecimal.ONE;
            GridStrategyConfig.OrderSide closeSide;
            BigDecimal targetClosePrice;

            // 2. 根据成交方向计算平仓价格 (基于开仓价)
            if (filledGridLevel.getSide() == GridStrategyConfig.OrderSide.BUY) {
                // 买单开多成交 -> 需要卖出平多 (SELL)
                closeSide = GridStrategyConfig.OrderSide.SELL;
                // Python: close_price = filled_grid.price * (Decimal("1") + profit_offset)
                targetClosePrice = filledGridLevel.getPrice().multiply(ONE.add(profitOffset));
            } else {
                // 卖单开空成交 -> 需要买入平空 (BUY)
                closeSide = GridStrategyConfig.OrderSide.BUY;
                // Python: close_price = filled_grid.price * (Decimal("1") - profit_offset)
                targetClosePrice = filledGridLevel.getPrice().multiply(ONE.subtract(profitOffset));
            }

            // 3. 创建平仓网格层级 (标记 isCloseOrder = true)
            GridStrategyConfig.GridLevel closeGridLevel = new GridStrategyConfig.GridLevel(
                    targetClosePrice,
                    filledGridLevel.getSize(),
                    closeSide,
                    true // 标记为平仓单
            );

            // 4. 挂平仓单
            // Python 中使用 OrderType.POST_ONLY，Java 版本也保持一致
            GridStrategyConfig.Order closeOrder = new GridStrategyConfig.Order(
                    thirdAccountId,
                    contractId,
                    closeSide,
                    GridStrategyConfig.OrderType.LIMIT,
                    filledGridLevel.getSize(),
                    targetClosePrice,
                    GridStrategyConfig.leverage
            );

            // API限速保护
            sleepApiInterval();

            String orderId = edgeXClient.placeOrder(closeOrder);
            if (orderId != null) {
                closeGridLevel.setOrderId(orderId);
                // 修正点 2：将平仓单也放入 pendingOrders 中跟踪 (Redis 操作)
                gridMgr.addPendingOrder(orderId, closeGridLevel);
                log.info("{},{} 挂平仓单: {} {} @ {}", thirdAccountId, contractId, closeSide, filledGridLevel.getSize(), targetClosePrice);
            }

        } catch (Exception e) {
            log.error("{},{} 挂平仓单失败: {}", thirdAccountId, contractId, e.getMessage(), e);
        }
    }

    private void sleepApiInterval() {
        try {
            Thread.sleep((long) (GridStrategyConfig.apiCallInterval * 1000));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

}
