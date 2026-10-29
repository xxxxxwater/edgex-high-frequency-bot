"""EdgeXClient.get_account_info：按官方 SDK 的 getAccountAsset 响应结构解析"""

from unittest.mock import AsyncMock, patch

import pytest

import edgex_client
from edgex_types import TradeDirection
from tests.helpers import make_config


def _response(position_list=None, collateral=None):
    # 结构参考 edgex-golang-sdk sdk/account/types.go 与 client_test.go
    data = {
        "positionList": position_list or [],
        "collateralList": [{"coinId": "1000", "amount": "1000"}],
        "positionAssetList": [],
        "collateralAssetModelList": [collateral or {"coinId": "1000", "totalEquity": "1050.5", "availableBalance": "800.25"}],
    }
    return {"code": "SUCCESS", "data": data}


@pytest.fixture
async def client():
    with patch.object(edgex_client.EdgeXClient, "_init_contract_cache", AsyncMock()):
        c = edgex_client.EdgeXClient(make_config(leverage=20))
    c.sdk_client.account.get_account_asset = AsyncMock(return_value=_response())
    return c


async def test_balances_from_collateral_asset_model(client):
    # 之前读 data.totalEquity / data.availableBalance（不存在）-> 余额恒为 0
    info = await client.get_account_info()
    assert info.balance == 1050.5
    assert info.available_balance == 800.25
    assert info.positions == {}


async def test_long_and_short_positions_from_signed_open_size(client):
    # 之前读 positionSize / positionSide / avgEntryPrice（不存在）-> 持仓恒为空
    client.sdk_client.account.get_account_asset.return_value = _response([
        {"contractId": "10000003", "openSize": "1.5", "openValue": "150.3", "createdTime": "1700000000123"},
        {"contractId": "10000001", "openSize": "-0.002", "openValue": "-130", "createdTime": "1700000000000"},
        {"contractId": "10000002", "openSize": "0", "openValue": "0"},
    ])
    info = await client.get_account_info()

    assert set(info.positions) == {"10000003", "10000001"}
    sol = info.positions["10000003"]
    assert sol.direction == TradeDirection.LONG
    assert sol.size == 1.5
    assert sol.entry_price == pytest.approx(100.2)
    assert sol.leverage == 20
    assert sol.opening_time == 1700000000
    btc = info.positions["10000001"]
    assert btc.direction == TradeDirection.SHORT
    assert btc.size == 0.002
    assert btc.entry_price == pytest.approx(65000)


async def test_single_request_per_refresh(client):
    client.sdk_client.account.get_account_positions = AsyncMock()
    await client.get_account_info()
    client.sdk_client.account.get_account_asset.assert_awaited_once()
    client.sdk_client.account.get_account_positions.assert_not_awaited()


async def test_missing_balance_fields_fail_instead_of_zero(client):
    client.sdk_client.account.get_account_asset.return_value = {"code": "SUCCESS", "data": {"positionList": []}}
    with pytest.raises(ValueError, match="collateralAssetModelList"):
        await client.get_account_info()


async def test_unparseable_position_fails_instead_of_flat(client):
    # 不能把看不懂的持仓当成"无持仓"，否则策略会在已有持仓时继续开仓
    client.sdk_client.account.get_account_asset.return_value = _response([{"contractId": "10000003", "foo": "1"}])
    with pytest.raises(ValueError, match="openSize"):
        await client.get_account_info()


async def test_error_code_raises(client):
    client.sdk_client.account.get_account_asset.return_value = {"code": "FAILED"}
    with pytest.raises(ValueError):
        await client.get_account_info()
