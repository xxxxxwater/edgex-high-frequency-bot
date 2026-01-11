package com.tradez.order.common.strategy.py38;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONArray;
import com.alibaba.fastjson.JSONObject;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.edgex.exchange.model.ContractModel;
import com.tradez.common.constant.RedisKeyGener;
import com.tradez.common.enums.CommonCodeEnum;
import com.tradez.common.enums.order.OrderSideEnum;
import com.tradez.common.enums.order.OrderTypeEnum;
import com.tradez.common.exception.AppServerException;
import com.tradez.common.util.AesAppPinCodeUtil;
import com.tradez.common.util.AesGcmUtil;
import com.tradez.common.util.OrderNoUtils;
import com.tradez.model.AccountKey;
import com.tradez.model.Order;
import com.tradez.model.ThirdContract;
import com.tradez.order.common.edgex.api.EdgeXApiClient;
import com.tradez.order.common.edgex.api.URI;
import com.tradez.order.common.edgex.mode.ApiResponse;
import com.tradez.order.common.edgex.mode.req.AccountAssetReq;
import com.tradez.order.common.edgex.mode.req.CancelOrderReq;
import com.tradez.order.common.edgex.mode.req.OrderCreateRequest;
import com.tradez.order.common.edgex.mode.req.OrderSizeCreateQueryReq;
import com.tradez.order.common.edgex.mode.req.UpdateLeverageSetReq;
import com.tradez.order.common.edgex.mode.res.AccountAssetRes;
import com.tradez.order.common.edgex.mode.res.OrderResponse;
import com.tradez.order.common.edgex.mode.res.OrderSizeCreateQueryRes;
import com.tradez.order.common.edgex.utils.OrderUtil;
import com.tradez.order.mapper.AccountKeyMapper;
import com.tradez.order.mapper.OrderMapper;
import com.tradez.order.mapper.ThirdContractMapper;

import org.apache.commons.collections4.CollectionUtils;
import org.apache.commons.lang3.StringUtils;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.TimeUnit;

import javax.annotation.Resource;

import cn.hutool.http.HttpUtil;
import cn.hutool.json.JSONUtil;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
public class EdgeXClientImpl implements EdgeXClient {

    private static final String CODE = "SUCCESS";
    private static final String GET = "GET";
    private static final String ORDER_SUF = "5";

    @Resource
    AccountKeyMapper accountKeyMapper;
    @Resource
    ThirdContractMapper thirdContractMapper;
    @Resource
    StringRedisTemplate stringRedisTemplate;
    @Resource
    private OrderMapper orderMapper;

    @Override
    public GridStrategyConfig.OrderBook getOrderBook(String contractId, int depth) {
        String respDataStr = HttpUtil.createGet(URI.BASE_URL + URI.GET_DEPTH)
                .form("contractId", contractId)
                .form("level", depth)
                .execute().body();
        ApiResponse apiResponse = JSONUtil.toBean(respDataStr, ApiResponse.class);
        if (!CODE.equalsIgnoreCase(apiResponse.getCode())) {
            return GridStrategyConfig.OrderBook.builder().build();
        }
//        JSONObject jsonObject = JSONObject.parseObject(JSON.toJSONString(apiResponse.getData()));
        JSONArray jsonArray = JSONArray.parseArray(JSON.toJSONString(apiResponse.getData()));
        JSONObject jsonObject = JSONObject.parseObject(JSONArray.toJSONString(jsonArray.get(0)));
        JSONArray asksArr = jsonObject.getJSONArray("asks");
        JSONArray bidsArr = jsonObject.getJSONArray("bids");
        return GridStrategyConfig.OrderBook.builder()
                .asks(asksArr.toJavaList(GridStrategyConfig.OrderBook.Level.class))
                .bids(bidsArr.toJavaList(GridStrategyConfig.OrderBook.Level.class))
                .build();
    }

    @Override
    public OrderSizeCreateQueryRes getMaxCreateOrderSize(String thirdAccountId, String contractId) {
        BigDecimal price = this.getClosePrice(contractId);
        if (Objects.isNull(price)) {
            return null;
        }
        AccountKey accountKey = getAccountKey(thirdAccountId);
        if (Objects.isNull(accountKey)) {
            return null;
        }
        String privateKey = accountKey.getPrivateKey();
        OrderSizeCreateQueryReq queryReq = OrderSizeCreateQueryReq.builder()
                .accountId(thirdAccountId).contractId(contractId)
                .price(price.toPlainString()).build();
        return EdgeXApiClient.getMaxCreateOrderSize(queryReq, privateKey);
    }

    @Override
    public List<String> getActiveOrderPage(String thirdAccountId, String contractId) throws AppServerException {
        //查询账户信息
        AccountKey accountKey = getAccountKey(thirdAccountId);
        if (Objects.isNull(accountKey)) {
            throw new AppServerException(CommonCodeEnum.FAIL);
        }
        String privateKey = accountKey.getPrivateKey();
        return EdgeXApiClient.getActiveOrderPage(privateKey, thirdAccountId, contractId);
    }

    @Override
    public String placeOrder(GridStrategyConfig.Order order) throws AppServerException {
        String thirdAccountId = order.getThirdAccountId();
        //查询账户信息
        AccountKey accountKey = getAccountKey(thirdAccountId);
        if (Objects.isNull(accountKey)) {
            throw new AppServerException(CommonCodeEnum.FAIL);
        }
        String privateKey = accountKey.getPrivateKey();

        //查询合约信息
        ContractModel contractModel = getContractModel(order.getContractId());
        if (Objects.isNull(contractModel)) {
            throw new AppServerException(CommonCodeEnum.FAIL);
        }

        //计算方向
        OrderSideEnum orderSideEnum = Objects.equals(order.getSide(), GridStrategyConfig.OrderSide.BUY) ? OrderSideEnum.BUY : OrderSideEnum.SELL;
        OrderTypeEnum orderTypeEnum = Objects.equals(order.getOrderType(), GridStrategyConfig.OrderType.MARKET) ? OrderTypeEnum.MARKET : OrderTypeEnum.LIMIT;

        //查询买一卖一价格
        OrderSizeCreateQueryRes queryRes = getMaxCreateOrderSize(thirdAccountId, order.getContractId());
        if (Objects.isNull(queryRes)) {
            throw new AppServerException(CommonCodeEnum.FAIL);
        }

        //获取价格
        BigDecimal price;
        String targetPrice;
        if (Objects.equals(orderTypeEnum, OrderTypeEnum.MARKET)) {
            price = getClosePrice(order.getContractId());
            targetPrice = Objects.equals(orderSideEnum, OrderSideEnum.BUY) ? queryRes.getAsk1Price() : queryRes.getBid1Price();
        } else {
            //查询合约信息
            price = OrderUtil.adjustToStepSize(order.getPrice(), new BigDecimal(contractModel.getTickSize())).stripTrailingZeros();
            targetPrice = price.toPlainString();
        }
        if (Objects.isNull(price)) {
            throw new AppServerException(CommonCodeEnum.FAIL);
        }
        BigDecimal orderSize = OrderUtil.adjustToStepSize(order.getQuantity(), new BigDecimal(contractModel.getStepSize()));

        //构建保存订单
        Order odr = new Order();
        odr.setOrderNo(OrderNoUtils.getOrderNo(ORDER_SUF));
        odr.setAccountId(accountKey.getAccountId());
        odr.setContractId(Long.valueOf(order.getContractId()));
        odr.setSide(orderSideEnum.getValue());
        odr.setSize(orderSize);
        odr.setContractName(contractModel.getContractName());
        odr.setType(orderTypeEnum.getValue());
        odr.setPrice(price);
        odr.setMaxLeverage(String.valueOf(order.getLeverage()));
        orderMapper.insert(odr);

        //修改杠杆
        UpdateLeverageSetReq leverageSetReq = new UpdateLeverageSetReq();
        leverageSetReq.setAccountId(accountKey.getThirdAccountId());
        leverageSetReq.setContractId(contractModel.getContractId());
        leverageSetReq.setLeverage(String.valueOf(order.getLeverage()));
        Boolean leverageResult = EdgeXApiClient.updateLeverageSetting(leverageSetReq, privateKey);
        log.info("[执行网格下单策略]第三方用户ID:{},修改杠杆结果:{}", accountKey.getThirdAccountId(), leverageResult);

        //构建下单
        OrderCreateRequest request = new OrderCreateRequest();
        request.setAccountId(order.getThirdAccountId());
        request.setOrderNo(odr.getOrderNo());
        request.setOpenTpSlParentOrderId(OrderNoUtils.getOrderNo());
        request.setStopLossOrderNo(OrderNoUtils.getOrderNo());
        request.setProfitOrderNo(OrderNoUtils.getOrderNo());
        request.setPrivateKeyHex(privateKey);
        request.setContractModel(contractModel);
        request.setOrderSide(orderSideEnum);
        request.setOrderPrice(price);
        request.setOrderSize(orderSize);
        request.setOrderType(orderTypeEnum);
        request.setTargetPrice(new BigDecimal(targetPrice).stripTrailingZeros());
        OrderResponse orderResponse;
        if (Objects.equals(orderTypeEnum, OrderTypeEnum.MARKET)) {
            orderResponse = EdgeXApiClient.createMarketOrder(request);
        } else {
            orderResponse = EdgeXApiClient.createLimitOrder(request);
        }
        if (Objects.isNull(orderResponse)) {
            throw new AppServerException(CommonCodeEnum.FAIL);
        }

        //更新订单状态
        odr.setThirdOrderId(orderResponse.getOrderId());
        orderMapper.updateById(odr);
        return orderResponse.getOrderId();
    }


    @Override
    public void cancelAllOrders(String thirdAccountId, String contractId) throws AppServerException {
        //查询账户信息
        AccountKey accountKey = getAccountKey(thirdAccountId);
        if (Objects.isNull(accountKey)) {
            throw new AppServerException(CommonCodeEnum.FAIL);
        }
        String privateKey = accountKey.getPrivateKey();
        List<String> orderIdList = EdgeXApiClient.getActiveOrderPage(privateKey, thirdAccountId, contractId);
        if (CollectionUtils.isEmpty(orderIdList)) {
            log.info("[取消所有订单]第三方用户ID:{},无未完成订单", thirdAccountId);
           return;
        }
        for(String orderId: orderIdList) {
            CancelOrderReq cancelOrderReq = CancelOrderReq.builder()
                    .accountId(thirdAccountId)
                    .orderIdList(Collections.singletonList(orderId))
                    .build();
            boolean bool = EdgeXApiClient.cancelOrderById(cancelOrderReq, privateKey);
            if (!bool) {
                throw new AppServerException(CommonCodeEnum.FAIL);
            }
        }
    }

    @Override
    public void cancelOrder(String thirdAccountId, String contractId, String orderId) throws AppServerException {
        //查询账户信息
        AccountKey accountKey = getAccountKey(thirdAccountId);
        if (Objects.isNull(accountKey)) {
            throw new AppServerException(CommonCodeEnum.FAIL);
        }
        String privateKey = accountKey.getPrivateKey();
        CancelOrderReq cancelOrderReq = CancelOrderReq.builder()
                .accountId(thirdAccountId)
                .orderIdList(Collections.singletonList(orderId))
                .build();
        boolean bool = EdgeXApiClient.cancelOrderById(cancelOrderReq, privateKey);
        if (!bool) {
            throw new AppServerException(CommonCodeEnum.FAIL);
        }
    }


    @Override
    public BigDecimal getBalance(String thirdAccountId) {
        return getBalance(thirdAccountId, null);
    }

    @Override
    public BigDecimal getBalance(String thirdAccountId, String contractId) {
        //查询账户信息
        AccountKey accountKey = getAccountKey(thirdAccountId);
        if (Objects.isNull(accountKey)) {
            return BigDecimal.ZERO;
        }
        String privateKey = accountKey.getPrivateKey();
        AccountAssetReq param = AccountAssetReq.builder()
                .accountId(thirdAccountId)
                .privateKey(privateKey)
                .timestamp(System.currentTimeMillis())
                .build();
        AccountAssetRes res = EdgeXApiClient.getAccountAsset(param);
        if (Objects.isNull(res) || CollectionUtils.isEmpty(res.getCollateralList())) {
            return BigDecimal.ZERO;
        }
        return new BigDecimal(res.getCollateralList().get(0).getAmount());
    }

    @Override
    public int pendingOrders(String thirdAccountId, String contractId) {
        //查询账户信息
        AccountKey accountKey = getAccountKey(thirdAccountId);
        if (Objects.isNull(accountKey)) {
            return 0;
        }
        String privateKey = accountKey.getPrivateKey();
        List<String> orderIdList = EdgeXApiClient.getActiveOrderPage(privateKey, thirdAccountId, contractId);
        if (CollectionUtils.isEmpty(orderIdList)) {
            return 0;
        }
        return orderIdList.size();
    }


    /**
     * 查询合约信息
     */
    private ContractModel getContractModel(String contractId) {
        ThirdContract thirdContract = thirdContractMapper.selectOne(Wrappers.lambdaQuery(ThirdContract.class)
                .eq(ThirdContract::getContractId, contractId)
                .last("limit 1"));
        if (Objects.isNull(thirdContract)) {
            return null;
        }
        String contractKey = RedisKeyGener.getCacheSupportContractKey(thirdContract.getId().toString());
        String contractStr = stringRedisTemplate.opsForValue().get(contractKey);
        if (StringUtils.isBlank(contractStr)) {
            return null;
        }
        return JSONUtil.toBean(contractStr, ContractModel.class);
    }


    /**
     * 查询账户信息
     */
    private AccountKey getAccountKey(String thirdAccountId) {
        String redisKey = "data:account:key:" + thirdAccountId;
        String accountKeyStr = stringRedisTemplate.opsForValue().get(redisKey);
        if (StringUtils.isNotBlank(accountKeyStr)) {
            AccountKey accountKey = JSONObject.parseObject(accountKeyStr, AccountKey.class);
            String keyData = AesGcmUtil.getKey32(accountKey.getAccountId() + AesAppPinCodeUtil.SUFFIX);
            String privateKey = AesGcmUtil.decrypt(accountKey.getPrivateKey(), keyData);
            accountKey.setPrivateKey(privateKey);
            return accountKey;
        }
        AccountKey accountKey = accountKeyMapper.selectOne(Wrappers.lambdaQuery(AccountKey.class)
                .eq(AccountKey::getThirdAccountId, thirdAccountId).last("limit 1"));
        if (Objects.isNull(accountKey)) {
            return null;
        }
        stringRedisTemplate.opsForValue().set(redisKey, JSONObject.toJSONString(accountKey), 1, TimeUnit.DAYS);
        String keyData = AesGcmUtil.getKey32(accountKey.getAccountId() + AesAppPinCodeUtil.SUFFIX);
        String privateKey = AesGcmUtil.decrypt(accountKey.getPrivateKey(), keyData);
        accountKey.setPrivateKey(privateKey);
        return accountKey;
    }

    /**
     * 获取最新价
     */
    private BigDecimal getClosePrice(String contractId) {
        String klineKey = "kline:" + contractId + ":MINUTE_1:last";
        String klineStr = stringRedisTemplate.opsForValue().get(klineKey);
        if (StringUtils.isBlank(klineStr)) {
            return null;
        }
        JSONObject klineJson = JSONObject.parseObject(klineStr);
        return klineJson.getBigDecimal("close");
    }

}
