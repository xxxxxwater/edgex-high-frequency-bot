"""EdgeXClient.place_order：使用真实 SDK 签名逻辑，只 mock 网络层"""

from unittest.mock import AsyncMock, patch

import pytest

import edgex_client
from edgex_types import Order, OrderSide, OrderType
from tests.helpers import make_config

# 64 位十六进制的假私钥，仅用于离线计算签名
FAKE_STARK_KEY = "1" * 64

METADATA = {
    "code": "SUCCESS",
    "data": {
        "global": {"starkExCollateralCoin": {"starkExAssetId": "0x1"}},
        "contractList": [{
            "contractId": "10000003",
            "contractName": "SOLUSD",
            "tickSize": "0.01",
            "stepSize": "0.1",
            "minOrderSize": "0.3",
            "starkExResolution": "0x989680",
            "starkExSyntheticAssetId": "0x2",
            "defaultTakerFeeRate": "0.00038",
        }],
    },
}


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(edgex_client.EdgeXClient, "_contract_id_cache", {"SOLUSD": "10000003", "10000003": "10000003"})
    monkeypatch.setattr(edgex_client.EdgeXClient, "_cache_initialized", True)
    with patch.object(edgex_client.EdgeXClient, "_init_contract_cache", AsyncMock()):
        c = edgex_client.EdgeXClient(make_config(stark_private_key=FAKE_STARK_KEY))
    c.sdk_client.get_metadata = AsyncMock(return_value=METADATA)
    c.sdk_client.get_24_hour_quote = AsyncMock(return_value={"code": "SUCCESS", "data": [{"oraclePrice": "150.123"}]})
    c.sdk_client.async_client.make_authenticated_request = AsyncMock(return_value={"code": "SUCCESS", "data": {}})
    return c


def _sent(client):
    return client.sdk_client.async_client.make_authenticated_request.call_args.kwargs["data"]


def _order(**kw):
    params = dict(symbol="SOL-USDT", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=15.0, leverage=50)
    params.update(kw)
    return Order(**params)


async def test_symbol_name_is_resolved_to_contract_id(client):
    # 之前直接把 "SOL-USDT" 当合约ID传给 SDK -> ValueError: contract not found
    await client.place_order(_order())
    data = _sent(client)
    assert data["contractId"] == "10000003"
    assert data["side"] == "BUY"
    assert data["type"] == "MARKET"
    assert data["reduceOnly"] is False


async def test_market_buy_signs_with_oracle_based_price(client):
    # 之前市价单价格固定为 "0"，l2Value / l2LimitFee 都是 0
    await client.place_order(_order(quantity=2.0))
    data = _sent(client)
    # oraclePrice * 10，按 tickSize 精度取整
    assert data["l2Value"] == "3002.46"
    assert int(data["l2LimitFee"]) > 0


async def test_market_sell_uses_tick_size_price_and_reduce_only(client):
    await client.place_order(_order(side=OrderSide.SELL, quantity=1.0, reduce_only=True))
    data = _sent(client)
    assert data["side"] == "SELL"
    assert data["l2Value"] == "0.01"
    assert data["reduceOnly"] is True
    client.sdk_client.get_24_hour_quote.assert_not_awaited()


@pytest.mark.parametrize("quantity, expected", [
    (0.37, "0.3"),                  # 向下对齐 stepSize，不超出策略计算的数量
    (0.30000000000000004, "0.3"),   # float 长尾
    (15.0, "15"),
])
async def test_size_is_rounded_down_to_step(client, quantity, expected):
    await client.place_order(_order(quantity=quantity))
    assert _sent(client)["size"] == expected


async def test_size_below_exchange_minimum_is_rejected_locally(client):
    with pytest.raises(ValueError, match="最小下单量"):
        await client.place_order(_order(quantity=0.29))
    client.sdk_client.async_client.make_authenticated_request.assert_not_awaited()


async def test_unknown_symbol_is_rejected_without_request(client, monkeypatch):
    with pytest.raises(ValueError, match="合约ID"):
        await client.place_order(_order(symbol="FOO-USDT"))
    client.sdk_client.async_client.make_authenticated_request.assert_not_awaited()


async def test_exchange_error_is_raised(client):
    client.sdk_client.async_client.make_authenticated_request.return_value = {
        "code": "FAILED", "errorParam": {"message": "insufficient margin"}}
    with pytest.raises(ValueError, match="insufficient margin"):
        await client.place_order(_order())
