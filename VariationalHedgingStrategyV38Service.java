package com.tradez.order.common.strategy.py38;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;

import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
public class VariationalHedgingStrategyV38Service {

    private static final BigDecimal MIN_HEDGE_NOTIONAL = new BigDecimal("50");
    private static final BigDecimal OPEN_EQUITY_CHANGE_PCT = new BigDecimal("0.01");
    private static final BigDecimal EXIT_TAKE_PROFIT_PCT = new BigDecimal("0.01");
    private static final BigDecimal EXIT_STOP_LOSS_PCT = new BigDecimal("-0.02");
    private static final long EQUITY_SAMPLE_INTERVAL_SEC = 15 * 60;

    private final Map<String, BigDecimal> lastEquityMap = new ConcurrentHashMap<>();
    private final Map<String, Long> lastEquityTsMap = new ConcurrentHashMap<>();
    private final Map<String, BigDecimal> lastEquityChangePctMap = new ConcurrentHashMap<>();

    @Resource
    EdgeXClient edgeXClient;

    @Resource
    StringRedisTemplate stringRedisTemplate;

    public void executeStrategy(List<String> thirdAccountIds, List<String> contractIdList) {
        GridStrategyConfig config = new GridStrategyConfig();
        if (contractIdList == null || contractIdList.size() < 2) {
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

                String[] pairContracts = selectPairContracts(contractIdList, orderBookMap, midPriceMap);
                if (pairContracts == null) {
                    log.warn("hedge skip, pair contracts not ready: {}, {}", thirdAccountId, contractIdList);
                    continue;
                }

                String contractA = pairContracts[0];
                String contractB = pairContracts[1];
                SymbolGridManager gridA = gridMgrMap.get(contractA);
                SymbolGridManager gridB = gridMgrMap.get(contractB);
                GridStrategyConfig.OrderBook bookA = orderBookMap.get(contractA);
                GridStrategyConfig.OrderBook bookB = orderBookMap.get(contractB);
                BigDecimal midA = midPriceMap.get(contractA);
                BigDecimal midB = midPriceMap.get(contractB);
                if (gridA == null || gridB == null || bookA == null || bookB == null || midA == null || midB == null) {
                    continue;
                }

                BigDecimal posA = getHedgePosition(thirdAccountId, contractA);
                BigDecimal posB = getHedgePosition(thirdAccountId, contractB);
                boolean hasPosition = posA.signum() != 0 || posB.signum() != 0;

                EquitySample equitySample = sampleEquityChange(thirdAccountId, equity);
                if (equitySample.updated) {
                    if (hasPosition && shouldExitPair(equitySample.pctChange)) {
                        sleepApiInterval();
                        cancelOpenOrders(gridA, thirdAccountId, contractA);
                        sleepApiInterval();
                        cancelOpenOrders(gridB, thirdAccountId, contractB);

                        sleepApiInterval();
                        closePairPositions(thirdAccountId, gridA, contractA, bookA, posA);
                        sleepApiInterval();
                        closePairPositions(thirdAccountId, gridB, contractB, bookB, posB);
                    } else if (!hasPosition && shouldOpenPair(equitySample.pctChange)) {
                        if (!hasPendingOrders(gridA) && !hasPendingOrders(gridB)) {
                            sleepApiInterval();
                            openPairPositions(thirdAccountId, gridA, contractA, bookA, midA,
                                    gridB, contractB, bookB, midB, equitySample.pctChange, equity);
                        }
                    }
                }

                String keyA = hedgeKey(thirdAccountId, contractA, "last_mid_price");
                stringRedisTemplate.opsForValue().set(keyA, midA.toPlainString());
                stringRedisTemplate.opsForValue().set(keyA + ":last_update_time", String.valueOf(System.currentTimeMillis() / 1000));
                String keyB = hedgeKey(thirdAccountId, contractB, "last_mid_price");
                stringRedisTemplate.opsForValue().set(keyB, midB.toPlainString());
                stringRedisTemplate.opsForValue().set(keyB + ":last_update_time", String.valueOf(System.currentTimeMillis() / 1000));

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

    private String[] selectPairContracts(List<String> contractIdList,
                                         Map<String, GridStrategyConfig.OrderBook> orderBookMap,
                                         Map<String, BigDecimal> midPriceMap) {
        String first = null;
        String second = null;
        for (String contractId : contractIdList) {
            if (orderBookMap.get(contractId) == null || midPriceMap.get(contractId) == null) {
                continue;
            }
            if (first == null) {
                first = contractId;
            } else {
                second = contractId;
                break;
            }
        }
        if (first == null || second == null) {
            return null;
        }
        return new String[]{first, second};
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

    private void openPairPositions(String thirdAccountId,
                                   SymbolGridManager gridA, String contractA, GridStrategyConfig.OrderBook bookA, BigDecimal midA,
                                   SymbolGridManager gridB, String contractB, GridStrategyConfig.OrderBook bookB, BigDecimal midB,
                                   BigDecimal equityChangePct, BigDecimal equity) {
        try {
            GridStrategyConfig.OrderBook.Level bestBidA = bookA.getBestBid();
            GridStrategyConfig.OrderBook.Level bestAskA = bookA.getBestAsk();
            GridStrategyConfig.OrderBook.Level bestBidB = bookB.getBestBid();
            GridStrategyConfig.OrderBook.Level bestAskB = bookB.getBestAsk();
            if (bestBidA == null || bestAskA == null || bestBidB == null || bestAskB == null) {
                return;
            }

            if (!gridA.canPlaceOrder() || !gridB.canPlaceOrder()) {
                return;
            }

            BigDecimal notional = equity.multiply(GridStrategyConfig.hedgeOrderSizePct);
            if (notional.compareTo(MIN_HEDGE_NOTIONAL) < 0) {
                return;
            }

            BigDecimal minNotionalA = GridStrategyConfig.getMinOrderSize(contractA).multiply(midA);
            BigDecimal minNotionalB = GridStrategyConfig.getMinOrderSize(contractB).multiply(midB);
            BigDecimal targetNotional = notional.max(minNotionalA).max(minNotionalB);

            BigDecimal sizeA = targetNotional.divide(midA, 8, RoundingMode.HALF_UP);
            BigDecimal sizeB = targetNotional.divide(midB, 8, RoundingMode.HALF_UP);

            boolean buyA = equityChangePct.compareTo(BigDecimal.ZERO) >= 0;
            String buyContract = buyA ? contractA : contractB;
            String sellContract = buyA ? contractB : contractA;
            SymbolGridManager buyMgr = buyA ? gridA : gridB;
            SymbolGridManager sellMgr = buyA ? gridB : gridA;
            GridStrategyConfig.OrderBook buyBook = buyA ? bookA : bookB;
            GridStrategyConfig.OrderBook sellBook = buyA ? bookB : bookA;
            BigDecimal buySize = buyA ? sizeA : sizeB;
            BigDecimal sellSize = buyA ? sizeB : sizeA;

            GridStrategyConfig.OrderBook.Level buyBid = buyBook.getBestBid();
            GridStrategyConfig.OrderBook.Level sellAsk = sellBook.getBestAsk();
            if (buyBid == null || sellAsk == null) {
                return;
            }

            GridStrategyConfig.GridLevel buyLevel = new GridStrategyConfig.GridLevel(
                    buyBid.getPrice(),
                    buySize,
                    GridStrategyConfig.OrderSide.BUY
            );
            String buyOrderId = edgeXClient.placeOrder(new GridStrategyConfig.Order(
                    thirdAccountId,
                    buyContract,
                    GridStrategyConfig.OrderSide.BUY,
                    GridStrategyConfig.OrderType.LIMIT,
                    buySize,
                    buyBid.getPrice(),
                    GridStrategyConfig.leverage
            ));
            sleepApiInterval();
            if (buyOrderId == null) {
                return;
            }
            buyLevel.setOrderId(buyOrderId);
            buyMgr.addPendingOrder(buyOrderId, buyLevel);
            buyMgr.updateOrderTime();

            GridStrategyConfig.GridLevel sellLevel = new GridStrategyConfig.GridLevel(
                    sellAsk.getPrice(),
                    sellSize,
                    GridStrategyConfig.OrderSide.SELL
            );
            String sellOrderId = edgeXClient.placeOrder(new GridStrategyConfig.Order(
                    thirdAccountId,
                    sellContract,
                    GridStrategyConfig.OrderSide.SELL,
                    GridStrategyConfig.OrderType.LIMIT,
                    sellSize,
                    sellAsk.getPrice(),
                    GridStrategyConfig.leverage
            ));
            sleepApiInterval();
            if (sellOrderId == null) {
                sleepApiInterval();
                edgeXClient.cancelOrder(thirdAccountId, buyContract, buyOrderId);
                buyMgr.removePendingOrder(buyOrderId);
                return;
            }
            sellLevel.setOrderId(sellOrderId);
            sellMgr.addPendingOrder(sellOrderId, sellLevel);
            sellMgr.updateOrderTime();
        } catch (Exception e) {
            log.error("hedge open pair error: {}, {}", thirdAccountId, contractA + "/" + contractB, e);
        }
    }

    private void closePairPositions(String thirdAccountId, SymbolGridManager gridMgr, String contractId,
                                    GridStrategyConfig.OrderBook orderBook, BigDecimal position) {
        try {
            if (position.signum() == 0) {
                return;
            }
            GridStrategyConfig.OrderBook.Level bestBid = orderBook.getBestBid();
            GridStrategyConfig.OrderBook.Level bestAsk = orderBook.getBestAsk();
            if (bestBid == null || bestAsk == null) {
                return;
            }
            if (!gridMgr.canPlaceOrder()) {
                return;
            }
            GridStrategyConfig.OrderSide side = position.signum() > 0
                    ? GridStrategyConfig.OrderSide.SELL
                    : GridStrategyConfig.OrderSide.BUY;
            BigDecimal size = position.abs();
            BigDecimal price = side == GridStrategyConfig.OrderSide.BUY ? bestBid.getPrice() : bestAsk.getPrice();

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
            log.error("hedge close order error: {}, {}", thirdAccountId, contractId, e);
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

    private boolean shouldOpenPair(BigDecimal equityChangePct) {
        return equityChangePct.compareTo(OPEN_EQUITY_CHANGE_PCT) >= 0;
    }

    private boolean shouldExitPair(BigDecimal equityChangePct) {
        return equityChangePct.compareTo(EXIT_TAKE_PROFIT_PCT) >= 0
                || equityChangePct.compareTo(EXIT_STOP_LOSS_PCT) <= 0;
    }

    private boolean hasPendingOrders(SymbolGridManager gridMgr) {
        Map<String, GridStrategyConfig.GridLevel> pendingOrders = gridMgr.getAllPendingOrders();
        return pendingOrders != null && !pendingOrders.isEmpty();
    }

    private EquitySample sampleEquityChange(String thirdAccountId, BigDecimal currentEquity) {
        long now = System.currentTimeMillis() / 1000;
        Long lastTs = lastEquityTsMap.get(thirdAccountId);
        BigDecimal lastEquity = lastEquityMap.get(thirdAccountId);
        if (lastTs == null || lastEquity == null || lastEquity.compareTo(BigDecimal.ZERO) <= 0) {
            lastEquityMap.put(thirdAccountId, currentEquity);
            lastEquityTsMap.put(thirdAccountId, now);
            return new EquitySample(BigDecimal.ZERO, false);
        }
        if (now - lastTs < EQUITY_SAMPLE_INTERVAL_SEC) {
            BigDecimal cached = lastEquityChangePctMap.getOrDefault(thirdAccountId, BigDecimal.ZERO);
            return new EquitySample(cached, false);
        }
        BigDecimal pct = currentEquity.subtract(lastEquity)
                .divide(lastEquity, 8, RoundingMode.HALF_UP);
        lastEquityMap.put(thirdAccountId, currentEquity);
        lastEquityTsMap.put(thirdAccountId, now);
        lastEquityChangePctMap.put(thirdAccountId, pct);
        return new EquitySample(pct, true);
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

    private static class EquitySample {
        private final BigDecimal pctChange;
        private final boolean updated;

        private EquitySample(BigDecimal pctChange, boolean updated) {
            this.pctChange = pctChange;
            this.updated = updated;
        }
    }
}
