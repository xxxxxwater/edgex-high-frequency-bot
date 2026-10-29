"""测试辅助：构造不访问网络的策略实例"""

import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import strategy as strategy_module
from config import Config
from edgex_types import AccountInfo, PriceData


def make_config(**overrides) -> Config:
    params = dict(
        symbols=["SOL-USDT"],
        account_id="1",
        stark_private_key="0x1",  # 假密钥，仅用于通过校验
        testnet=True,
    )
    params.update(overrides)
    return Config(**params)


def price(p: float) -> PriceData:
    return PriceData(timestamp=int(time.time() * 1000), open=p, high=p, low=p, close=p, volume=0)


def set_prices(st, symbol: str, prices):
    """模拟刚收到 WebSocket 推送的价格历史（否则会被视为过期而改走 REST ticker）"""
    st.price_history[symbol] = list(prices)
    st._last_ws_price_ms[symbol] = st._now_ms()


def make_strategy(config: Config = None, balance: str = "1000", positions=None):
    config = config or make_config()
    with patch.object(strategy_module, "EdgeXClient"):
        st = strategy_module.HighFrequencyStrategy(config)
    client = MagicMock()
    client.place_order = AsyncMock(return_value={"code": "SUCCESS", "data": {}})
    client.set_leverage = AsyncMock(return_value={"code": "SUCCESS"})
    client.get_contract_id_by_symbol = AsyncMock(side_effect=lambda s: {"SOL-USDT": "10000003", "BTC-USDT": "10000001"}.get(s))
    client.get_ticker = AsyncMock(side_effect=AssertionError("测试中不应访问 REST ticker"))
    client.get_account_info = AsyncMock(
        return_value=AccountInfo(balance=float(balance), available_balance=float(balance), positions=positions or {})
    )
    st.client = client
    st.balance = Decimal(balance)
    st.available_balance = Decimal(balance)
    return st
