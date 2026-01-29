package com.tradez.order.common.strategy.py38;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;

import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
public class VariationalHedgingStrategyV38Service {

    private static final BigDecimal NET_EXPOSURE_LIMIT_PCT = new BigDecimal("0.08");
    private static final BigDecimal MIN_HEDGE_NOTIONAL = new BigDecimal("50");

    @Resource
    EdgeXClient edgeXClient;

    @Resource
    StringRedisTemplate stringRedisTemplate;

    public void executeStrategy(List<String> thirdAccountIds, List<String> contractIdList) {
        GridStrategyConfig config = new GridStrategyConfig();
        if (contractIdList == null || contractIdList.isEmpty()) {
            return;
        }

        for (String thirdAccountId : thirdAccountIds) {
            try {
                Map<String, SymbolGridManager> gridMgrMap = new HashMap<>();
                Map<String, GridStrategyConfig.OrderBook> orderBookMap = new HashMap<>();
                Map<String, BigDecimal> midPriceMap = new HashMap<>();

                for (String contractId : contractIdList) {
                    SymbolGridManager gridMgr = new SymbolGridManager(stringRedisTemplate, contractId, thirdAccountId, config);
                    gridMgrMap.put(contractId, gridMgr);

                    sleepApiInterval();
                    GridStrategyConfig.OrderBook orderBook = edgeXClient.getOrderBook(contractId, GridStrategyConfig.depth);
                    if (orderBook == null) {
                        log.warn("hedge orderbook empty: {}, {}", thirdAccountId, contractId);
                        continue;
                    }

                    BigDecimal midPrice = orderBook.getMidPrice();
                    if (midPrice.compareTo(BigDecimal.ZERO) <= 0) {
                        log.warn("hedge mid price invalid: {}, {} {}", thirdAccountId, contractId, midPrice);
                        continue;
                    }

                    orderBookMap.put(contractId, orderBook);
                    midPriceMap.put(contractId, midPrice);
                }

                if (orderBookMap.size() < 2) {
                    log.warn("hedge skip, missing orderbooks: {}, {}", thirdAccountId, orderBookMap.keySet());
                    continue;
                }

                BigDecimal equity = edgeXClient.getBalance(thirdAccountId);
                if (equity.compareTo(BigDecimal.ZERO) <= 0) {
                    log.warn("hedge equity empty: {}", thirdAccountId);
                    continue;
                }

                Map<String, BigDecimal> posMap = new HashMap<>();
                BigDecimal netExposure = BigDecimal.ZERO;
                for (String contractId : contractIdList) {
                    BigDecimal pos = getHedgePosition(thirdAccountId, contractId);
                    BigDecimal midPrice = midPriceMap.get(contractId);
                    if (midPrice == null) {
                        continue;
                    }
                    posMap.put(contractId, pos);
                    netExposure = netExposure.add(pos.multiply(midPrice));
                }

                BigDecimal exposureLimit = equity.multiply(NET_EXPOSURE_LIMIT_PCT);
                boolean needHedge = netExposure.abs().compareTo(exposureLimit) > 0;

                if (needHedge) {
                    String hedgeContractId = selectHedgeContract(netExposure, contractIdList, posMap, midPriceMap);
                    if (hedgeContractId != null) {
                        SymbolGridManager gridMgr = gridMgrMap.get(hedgeContractId);
                        GridStrategyConfig.OrderBook orderBook = orderBookMap.get(hedgeContractId);
                        BigDecimal midPrice = midPriceMap.get(hedgeContractId);
                        if (gridMgr != null && orderBook != null && midPrice != null) {
                            BigDecimal hedgeNotional = netExposure.abs().subtract(exposureLimit);
                            if (hedgeNotional.compareTo(BigDecimal.ZERO) > 0) {
                                GridStrategyConfig.OrderSide side = netExposure.compareTo(BigDecimal.ZERO) > 0
                                        ? GridStrategyConfig.OrderSide.SELL
                                        : GridStrategyConfig.OrderSide.BUY;

                                generateHedgeOrder(thirdAccountId, gridMgr, hedgeContractId, midPrice, orderBook, side, hedgeNotional);

                                String key = hedgeKey(thirdAccountId, hedgeContractId, "last_mid_price");
                                stringRedisTemplate.opsForValue().set(key, midPrice.toPlainString());
                                stringRedisTemplate.opsForValue().set(key + ":last_update_time", String.valueOf(System.currentTimeMillis() / 1000));
                            }
                        }
                    }
                } else {
                    for (String contractId : contractIdList) {
                        SymbolGridManager gridMgr = gridMgrMap.get(contractId);
                        GridStrategyConfig.OrderBook orderBook = orderBookMap.get(contractId);
                        BigDecimal midPrice = midPriceMap.get(contractId);
                        if (gridMgr == null || orderBook == null || midPrice == null) {
                            continue;
                        }

                        boolean shouldRefresh = shouldRefreshGrid(thirdAccountId, contractId, midPrice);
                        if (shouldRefresh) {
                            sleepApiInterval();
                            cancelOpenOrders(gridMgr, thirdAccountId, contractId);

                            sleepApiInterval();
                            generatePairedOrders(thirdAccountId, gridMgr, contractId, midPrice, orderBook);

                            String key = hedgeKey(thirdAccountId, contractId, "last_mid_price");
                            stringRedisTemplate.opsForValue().set(key, midPrice.toPlainString());
                            stringRedisTemplate.opsForValue().set(key + ":last_update_time", String.valueOf(System.currentTimeMillis() / 1000));
                        }
                    }
                }

                for (String contractId : contractIdList) {
                    SymbolGridManager gridMgr = gridMgrMap.get(contractId);
                    if (gridMgr != null) {
                        sleepApiInterval();
                        checkFills(gridMgr, thirdAccountId, contractId);
                    }
                }
            } catch (Exception e) {
                log.error("hedge execute error", e);
            }
        }
    }

    private String selectHedgeContract(BigDecimal netExposure, List<String> contractIdList,
                                      Map<String, BigDecimal> posMap, Map<String, BigDecimal> midPriceMap) {
        BigDecimal bestNotional = BigDecimal.ZERO;
        String bestContract = null;
        for (String contractId : contractIdList) {
            BigDecimal pos = posMap.getOrDefault(contractId, BigDecimal.ZERO);
            BigDecimal mid = midPriceMap.get(contractId);
            if (mid == null) {
                continue;
            }
            BigDecimal notional = pos.multiply(mid);
            boolean isCandidate = netExposure.compareTo(BigDecimal.ZERO) > 0
                    ? notional.compareTo(BigDecimal.ZERO) > 0
                    : notional.compareTo(BigDecimal.ZERO) < 0;
            if (isCandidate) {
                BigDecimal absNotional = notional.abs();
                if (absNotional.compareTo(bestNotional) > 0) {
                    bestNotional = absNotional;
                    bestContract = contractId;
                }
            }
        }
        if (bestContract == null && !contractIdList.isEmpty()) {
            bestContract = contractIdList.get(0);
        }
        return bestContract;
    }

    private boolean shouldRefreshGrid(String thirdAccountId, String contractId, BigDecimal currentPrice) {
        int pendingOrdersCount = edgeXClient.pendingOrders(thirdAccountId, contractId);
        if (pendingOrdersCount == 0) {
            return true;
        }

        String key = hedgeKey(thirdAccountId, contractId, "last_mid_price");
        String priceStr = stringRedisTemplate.opsForValue().get(key);
        String timeStr = stringRedisTemplate.opsForValue().get(key + ":last_update_time");

        if (priceStr == null || timeStr == null) {
            return true;
        }

        try {
            BigDecimal lastMid = new BigDecimal(priceStr);
            long lastUpdate = Long.parseLong(timeStr);
            long now = System.currentTimeMillis() / 1000;

            if (lastMid.compareTo(BigDecimal.ZERO) > 0) {
                BigDecimal deviation = currentPrice.subtract(lastMid)
                        .abs()
                        .divide(lastMid, 8, RoundingMode.HALF_UP);
                if (deviation.compareTo(new BigDecimal("0.005")) > 0) {
                    if (now - lastUpdate < GridStrategyConfig.minRefreshIntervalOnDeviation) {
                        return false;
                    }
                    return true;
                }
            }

            if (now - lastUpdate > GridStrategyConfig.orderRefreshInterval) {
                return true;
            }
        } catch (Exception e) {
            log.error("hedge refresh check error: {}, {}", thirdAccountId, contractId, e);
            return false;
        }

        return false;
    }

    private void cancelOpenOrders(SymbolGridManager gridMgr, String thirdAccountId, String contractId) {
        try {
            Map<String, GridStrategyConfig.GridLevel> pendingOrders = gridMgr.getAllPendingOrders();
            for (Map.Entry<String, GridStrategyConfig.GridLevel> entry : pendingOrders.entrySet()) {
                String orderId = entry.getKey();
                edgeXClient.cancelOrder(thirdAccountId, contractId, orderId);
                gridMgr.removePendingOrder(orderId);
                sleepApiInterval();
            }
        } catch (Exception e) {
            log.error("hedge cancel open orders error: {}, {}", thirdAccountId, contractId, e);
        }
    }

    private void generatePairedOrders(String thirdAccountId, SymbolGridManager gridMgr, String contractId,
                                      BigDecimal midPrice, GridStrategyConfig.OrderBook orderBook) {
        try {
            BigDecimal balance = edgeXClient.getBalance(thirdAccountId, contractId);
            if (balance.compareTo(BigDecimal.ZERO) <= 0) {
                log.warn("hedge balance empty: {}, {}", thirdAccountId, contractId);
                return;
            }

            BigDecimal minSize = GridStrategyConfig.getMinOrderSize(contractId);
            BigDecimal orderValue = balance.multiply(GridStrategyConfig.hedgeOrderSizePct);
            BigDecimal size = orderValue.divide(midPrice, 8, RoundingMode.HALF_UP);
            if (size.compareTo(minSize) < 0) {
                size = minSize;
            }

            GridStrategyConfig.OrderBook.Level bestBid = orderBook.getBestBid();
            GridStrategyConfig.OrderBook.Level bestAsk = orderBook.getBestAsk();
            if (bestBid == null || bestAsk == null) {
                log.warn("hedge orderbook invalid: {}, {}", thirdAccountId, contractId);
                return;
            }

            if (!gridMgr.canPlaceOrder()) {
                return;
            }

            GridStrategyConfig.GridLevel buyLevel = new GridStrategyConfig.GridLevel(
                    bestBid.getPrice(),
                    size,
                    GridStrategyConfig.OrderSide.BUY
            );
            String buyOrderId = edgeXClient.placeOrder(new GridStrategyConfig.Order(
                    thirdAccountId,
                    contractId,
                    GridStrategyConfig.OrderSide.BUY,
                    GridStrategyConfig.OrderType.LIMIT,
                    size,
                    bestBid.getPrice(),
                    GridStrategyConfig.leverage
            ));
            sleepApiInterval();
            if (buyOrderId != null) {
                buyLevel.setOrderId(buyOrderId);
                gridMgr.addPendingOrder(buyOrderId, buyLevel);
                gridMgr.updateOrderTime();
            }

            if (!gridMgr.canPlaceOrder()) {
                return;
            }

            GridStrategyConfig.GridLevel sellLevel = new GridStrategyConfig.GridLevel(
                    bestAsk.getPrice(),
                    size,
                    GridStrategyConfig.OrderSide.SELL
            );
            String sellOrderId = edgeXClient.placeOrder(new GridStrategyConfig.Order(
                    thirdAccountId,
                    contractId,
                    GridStrategyConfig.OrderSide.SELL,
                    GridStrategyConfig.OrderType.LIMIT,
                    size,
                    bestAsk.getPrice(),
                    GridStrategyConfig.leverage
            ));
            sleepApiInterval();
            if (sellOrderId != null) {
                sellLevel.setOrderId(sellOrderId);
                gridMgr.addPendingOrder(sellOrderId, sellLevel);
                gridMgr.updateOrderTime();
            }
        } catch (Exception e) {
            log.error("hedge generate paired orders error: {}, {}", thirdAccountId, contractId, e);
        }
    }

    private void generateHedgeOrder(String thirdAccountId, SymbolGridManager gridMgr, String contractId,
                                    BigDecimal midPrice, GridStrategyConfig.OrderBook orderBook,
                                    GridStrategyConfig.OrderSide side, BigDecimal hedgeNotional) {
        try {
            if (hedgeNotional.compareTo(MIN_HEDGE_NOTIONAL) < 0) {
                log.info("hedge notional below min, skip: {}, {}, {}", thirdAccountId, contractId, hedgeNotional);
                return;
            }
            GridStrategyConfig.OrderBook.Level bestBid = orderBook.getBestBid();
            GridStrategyConfig.OrderBook.Level bestAsk = orderBook.getBestAsk();
            if (bestBid == null || bestAsk == null) {
                return;
            }

            BigDecimal price = side == GridStrategyConfig.OrderSide.BUY ? bestBid.getPrice() : bestAsk.getPrice();
            BigDecimal minSize = GridStrategyConfig.getMinOrderSize(contractId);
            BigDecimal size = hedgeNotional.divide(midPrice, 8, RoundingMode.HALF_UP)
                    .multiply(new BigDecimal("0.5"));
            if (size.compareTo(minSize) < 0) {
                size = minSize;
            }

            if (!gridMgr.canPlaceOrder()) {
                return;
            }

            GridStrategyConfig.GridLevel level = new GridStrategyConfig.GridLevel(price, size, side);
            String orderId = edgeXClient.placeOrder(new GridStrategyConfig.Order(
                    thirdAccountId,
                    contractId,
                    side,
                    GridStrategyConfig.OrderType.LIMIT,
                    size,
                    price,
                    GridStrategyConfig.leverage
            ));
            sleepApiInterval();
            if (orderId != null) {
                level.setOrderId(orderId);
                gridMgr.addPendingOrder(orderId, level);
                gridMgr.updateOrderTime();
            }
        } catch (Exception e) {
            log.error("hedge generate order error: {}, {}", thirdAccountId, contractId, e);
        }
    }

    private void checkFills(SymbolGridManager gridMgr, String thirdAccountId, String contractId) {
        try {
            Map<String, GridStrategyConfig.GridLevel> pendingOrders = gridMgr.getAllPendingOrders();
            List<String> activeOrders = edgeXClient.getActiveOrderPage(thirdAccountId, contractId);
            for (Map.Entry<String, GridStrategyConfig.GridLevel> entry : pendingOrders.entrySet()) {
                String orderId = entry.getKey();
                GridStrategyConfig.GridLevel gridLevel = entry.getValue();
                if (activeOrders == null || !activeOrders.contains(orderId)) {
                    updateHedgePosition(thirdAccountId, contractId, gridLevel);
                    gridMgr.removePendingOrder(orderId);
                }
            }
        } catch (Exception e) {
            log.error("hedge check fills error: {}, {}", thirdAccountId, contractId, e);
        }
    }

    private BigDecimal getHedgePosition(String thirdAccountId, String contractId) {
        String key = hedgePosKey(thirdAccountId, contractId);
        String value = stringRedisTemplate.opsForValue().get(key);
        if (value == null || value.isEmpty()) {
            return BigDecimal.ZERO;
        }
        try {
            return new BigDecimal(value);
        } catch (Exception e) {
            return BigDecimal.ZERO;
        }
    }

    private void updateHedgePosition(String thirdAccountId, String contractId, GridStrategyConfig.GridLevel gridLevel) {
        BigDecimal current = getHedgePosition(thirdAccountId, contractId);
        BigDecimal size = gridLevel.getSize();
        BigDecimal updated = gridLevel.getSide() == GridStrategyConfig.OrderSide.BUY
                ? current.add(size)
                : current.subtract(size);
        stringRedisTemplate.opsForValue().set(hedgePosKey(thirdAccountId, contractId), updated.toPlainString());
    }

    private String hedgeKey(String thirdAccountId, String contractId, String suffix) {
        return "hedge:strategy:" + thirdAccountId + ":" + contractId + ":" + suffix;
    }

    private String hedgePosKey(String thirdAccountId, String contractId) {
        return "hedge:pos:" + thirdAccountId + ":" + contractId;
    }

    private void sleepApiInterval() {
        try {
            Thread.sleep((long) (GridStrategyConfig.apiCallInterval * 1000));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
