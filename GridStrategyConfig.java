package com.tradez.order.common.strategy.py38;

import java.io.Serializable;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Data;

/**
 * 策略配置
 */
@Data
public class GridStrategyConfig implements Serializable {

    // 网格参数
    public static final int gridLevels = 3; // 网格层数（每侧）- 优化：增加到3层提高成交概率
    public static final BigDecimal gridSpacingPct = new BigDecimal("0.008"); // 0.8% - v3.8：千分之8
    public static final BigDecimal minGridSpacingPct = new BigDecimal("0.006"); // 最小间距 0.6%
    public static final BigDecimal maxGridSpacingPct = new BigDecimal("0.01"); // 最大间距 1.0%

    // 仓位管理（优化：降低杠杆和仓位，减少风险）
    public static final BigDecimal positionSizePct = new BigDecimal("0.09");
    public static final BigDecimal hedgeOrderSizePct = new BigDecimal("0.01"); // 每格仓位占净值3%到从9%
    public static final BigDecimal maxTotalPositionPct = new BigDecimal("0.5"); // 最大总持仓30%净值到50%
    public static final int leverage = 20; // 杠杆倍数（从10倍降低到3倍）

    // 风险控制
    public static final int maxPositionPerSide = 5; // 单侧最多持仓数量（从10降低到5）
    public static final BigDecimal stopLossPct = new BigDecimal("0.05"); // 2%止损（从1%放宽到5%）
    public static final BigDecimal dailyLossLimitPct = new BigDecimal("0.05"); // 5%日亏损限制

    // 订单管理
    public static final int orderRefreshInterval = 120; // 订单刷新间隔（秒）
    public static final double minOrderInterval = 2.5; // 最小下单间隔（秒）
    public static final int maxOpenOrders = 30; // 最大挂单数量
    public static final double apiCallInterval = 2.6; // API调用间隔（秒），必须 >= minOrderInterval

    // 深度
    public final static int depth = 15;

    // 各币种最小下单量
    private static Map<String, BigDecimal> MIN_ORDER_SIZES = Collections.unmodifiableMap(new HashMap<String, BigDecimal>() {{
        put("10000001", new BigDecimal("0.002"));//BTCUSD
        put("10000002", new BigDecimal("0.04"));//ETHUSD
        put("10000003", new BigDecimal("0.6"));//SOLUSD
        put("10000004", new BigDecimal("0.01"));//GRID-04
        put("10000005", new BigDecimal("0.01"));//GRID-05
        put("10000006", new BigDecimal("0.01"));//GRID-06
        put("10000064", new BigDecimal("0.2"));//BNBUSD
    }});

    /**
     * 【新增方法】 获取所有配置的合约ID列表
     */
    public static Set<String> getAllContractIds() {
        return MIN_ORDER_SIZES.keySet(); // 返回 Map 的键集合
    }

    public static BigDecimal getMinOrderSize(String contractId) {
        return MIN_ORDER_SIZES.getOrDefault(contractId, new BigDecimal("0.01"));
    }


    //网格交易策略中的一个层级
    @Data
    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public static class GridLevel implements Serializable {
        // 网格价格水平
        public final BigDecimal price;

        // 在该价格水平下的订单数量
        public final BigDecimal size;

        // 订单方向（买入或卖出）
        public final OrderSide side;

        // 是否为平仓订单标识
        public final boolean isCloseOrder;

        // 订单ID（可变，在订单创建后赋值）
        @JsonProperty("orderId")
        public String orderId;

        // 订单是否已成交标识
        @JsonProperty("isFilled")
        public boolean isFilled = false;

        // 订单成交时间戳
        @JsonProperty("filledTime")
        public long filledTime = 0;

        /**
         * 完整构造函数
         *
         * @param price        价格水平
         * @param size         订单数量
         * @param side         订单方向
         * @param isCloseOrder 是否为平仓订单
         */
        @JsonCreator
        public GridLevel(
                @JsonProperty("price") BigDecimal price,
                @JsonProperty("size") BigDecimal size,
                @JsonProperty("side") OrderSide side,
                @JsonProperty("isCloseOrder") boolean isCloseOrder) {
            this.price = price;
            this.size = size;
            this.side = side;
            this.isCloseOrder = isCloseOrder;
        }

        /**
         * 简化构造函数，默认为开仓订单
         *
         * @param price 价格水平
         * @param size  订单数量
         * @param side  订单方向
         */
        public GridLevel(BigDecimal price, BigDecimal size, OrderSide side) {
            this(price, size, side, false);
        }
    }


    // 简化版的持仓类
    @Data
    public static class Position implements Serializable {
        // 持仓数量
        private BigDecimal size = BigDecimal.ZERO;
        // 开仓价格（入场价格）
        private BigDecimal entryPrice = BigDecimal.ZERO;
        // 当前市场价格
        private BigDecimal currentPrice = BigDecimal.ZERO;
        // 未实现盈亏
        private BigDecimal unrealizedPnl = BigDecimal.ZERO;
        // 持仓方向（做多或做空）
        private TradeDirection direction = TradeDirection.LONG;
    }

    /**
     * 账户信息类
     * 包含账户余额和持仓信息
     */
    @Data
    public static class AccountInfo implements Serializable {
        // 账户余额
        private BigDecimal balance = BigDecimal.ZERO;

        // 持仓信息映射，键为交易对名称，值为对应的持仓对象
        private Map<String, Position> positions = new HashMap<>();
    }

    /**
     * 订单簿类，用于存储和管理买卖盘口数据
     */
    @Data
    @Builder
    public static class OrderBook implements Serializable {
        // 买单列表（按价格从高到低排序）
        private List<Level> bids = new ArrayList<>();
        // 卖单列表（按价格从低到高排序）
        private List<Level> asks = new ArrayList<>();

        /**
         * 价格层级类，表示订单簿中的一个价格点
         */
        @Data
        public static class Level implements Serializable {
            // 价格
            private final BigDecimal price;
            // 数量
            private final BigDecimal size;

            /**
             * 构造函数
             *
             * @param price 价格
             * @param size  数量
             */
            public Level(BigDecimal price, BigDecimal size) {
                this.price = price;
                this.size = size;
            }
        }

        /**
         * 添加买单到订单簿
         *
         * @param bid 买单
         */
        public void addBid(Level bid) {
            bids.add(bid);
        }

        /**
         * 添加卖单到订单簿
         *
         * @param ask 卖单
         */
        public void addAsk(Level ask) {
            asks.add(ask);
        }

        /**
         * 获取最佳买价（最高买价）
         *
         * @return 最佳买价，如果没有则返回null
         */
        public Level getBestBid() {
            return bids.isEmpty() ? null : bids.get(0);
        }

        /**
         * 获取最佳卖价（最低卖价）
         *
         * @return 最佳卖价，如果没有则返回null
         */
        public Level getBestAsk() {
            return asks.isEmpty() ? null : asks.get(0);
        }

        /**
         * 计算中间价格（买一和卖一的平均值）
         *
         * @return 中间价格，如果没有买卖报价则返回ZERO
         */
        public BigDecimal getMidPrice() {
            Level bestBid = getBestBid();
            Level bestAsk = getBestAsk();
            if (bestBid == null || bestAsk == null) {
                return BigDecimal.ZERO;
            }
            return bestBid.getPrice().add(bestAsk.getPrice())
                    .divide(BigDecimal.valueOf(2), 8, RoundingMode.HALF_UP);
        }
    }

    /**
     * 订单类，用于表示一个交易订单
     * 包含订单的基本信息，如交易对、方向、类型、数量、价格和杠杆等
     */
    @Data
    public static class Order implements Serializable {
        // 第三方账户ID
        private  String thirdAccountId;

        // 交易对符号，如 BTCUSDT, ETHUSDT 等
        private String contractId;

        // 订单方向，BUY 表示买入，SELL 表示卖出
        private OrderSide side;

        // 订单类型，如市价单(MARKET)、限价单(LIMIT)等
        private OrderType orderType;

        // 订单数量
        private BigDecimal quantity;

        // 订单价格（对于限价单有效）
        private BigDecimal price;

        // 杠杆倍数
        private int leverage;

        /**
         * 构造函数，用于创建一个新的订单对象
         *
         * @param contractId 交易对符号
         * @param side       订单方向
         * @param orderType  订单类型
         * @param quantity   订单数量
         * @param price      订单价格
         * @param leverage   杠杆倍数
         */
        public Order(String thirdAccountId, String contractId, OrderSide side, OrderType orderType,
                     BigDecimal quantity, BigDecimal price, int leverage) {
            this.thirdAccountId = thirdAccountId;
            this.contractId = contractId;
            this.side = side;
            this.orderType = orderType;
            this.quantity = quantity;
            this.price = price;
            this.leverage = leverage;
        }
    }

    // ===== 辅助枚举和类 =====

    public enum OrderSide {
        BUY, SELL
    }

    public enum OrderType {
        LIMIT, MARKET, POST_ONLY
    }

    public enum TradeDirection {
        LONG, SHORT
    }
}
