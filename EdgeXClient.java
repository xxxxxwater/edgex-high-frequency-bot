package com.tradez.order.common.strategy.py38;

import com.tradez.common.exception.AppServerException;
import com.tradez.order.common.edgex.mode.res.OrderSizeCreateQueryRes;

import java.math.BigDecimal;
import java.util.List;

public interface EdgeXClient {

    /**
     * 获取订单簿数据
     */
    GridStrategyConfig.OrderBook getOrderBook(String contractId, int depth);

    /**
     * 创建订单
     */
    String placeOrder(GridStrategyConfig.Order order) throws AppServerException;

    /**
     * 取消该交易对所有挂单
     */
    void cancelAllOrders(String thirdAccountId, String contractId) throws AppServerException;
    void cancelOrder(String thirdAccountId, String contractId,String orderId) throws AppServerException;

    /**
     * 获取账户余额
     */
    BigDecimal getBalance(String thirdAccountId, String contractId);

    /**
     * 获取账户余额
     */
    BigDecimal getBalance(String thirdAccountId);

    /**
     * 返回待成交的订单数量
     */
    int pendingOrders(String thirdAccountId, String contractId);

    /**
     * 获取该交易对所有账户可创建的订单最大数量
     * 买一卖一价
     */
    OrderSizeCreateQueryRes getMaxCreateOrderSize(String thirdAccountId, String contractId);

    /**
     * 当前合约订单
     */
    List<String> getActiveOrderPage(String thirdAccountId, String contractId) throws AppServerException;
}
