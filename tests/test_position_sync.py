"""持仓同步与重复下单防护"""

from unittest.mock import AsyncMock

from edgex_types import AccountInfo, Position, TradeDirection
from tests.helpers import make_config, make_strategy, price, set_prices


def _long_signal_history():
    # MA(5)=99.8，当前价 99 -> 偏离约 -0.8%，持续产生做多信号
    return [price(100)] * 4 + [price(99)]


def _sol_position(**kw):
    params = dict(symbol="10000003", direction=TradeDirection.LONG, size=1.0, entry_price=100.0,
                  stop_loss=0.0, take_profit=0.0, leverage=50, opening_time=0)
    params.update(kw)
    return Position(**params)


async def test_persistent_signal_does_not_reopen_every_loop():
    st = make_strategy()
    st.contract_ids["SOL-USDT"] = "10000003"
    clock = {"now": 1_000_000}
    st._now_ms = lambda: clock["now"]
    await st._update_account_info()

    # 模拟 run() 主循环 5 次（每次间隔 1 秒），交易所持仓尚未反映成交
    for _ in range(5):
        set_prices(st, "SOL-USDT", _long_signal_history())
        assert await st._refresh_account_if_needed()
        await st._execute_strategy_for_symbol("SOL-USDT")
        clock["now"] += 1000

    assert st.client.place_order.await_count == 1


async def test_reopen_allowed_only_after_cooldown_and_fresh_snapshot():
    st = make_strategy(make_config(min_trade_interval=5000))
    st.contract_ids["SOL-USDT"] = "10000003"
    st.price_history["SOL-USDT"] = _long_signal_history()
    clock = {"now": 1_000_000}
    st._now_ms = lambda: clock["now"]
    await st._update_account_info()

    await st._open_position("SOL-USDT", st._generate_signal("SOL-USDT", st.price_history["SOL-USDT"]), [])
    assert st.client.place_order.await_count == 1

    # 冷却期结束，但持仓快照还是下单后 1 秒时拍的 -> 仍不允许
    clock["now"] += 1000
    await st._update_account_info()
    clock["now"] += 5000
    assert not st._can_trade("SOL-USDT")

    # 冷却期结束后重新同步持仓 -> 允许
    await st._update_account_info()
    assert st._can_trade("SOL-USDT")


async def test_exchange_positions_are_keyed_by_symbol():
    st = make_strategy(positions={"10000003": _sol_position()})
    st.contract_ids["SOL-USDT"] = "10000003"
    await st._update_account_info()
    assert "SOL-USDT" in st.positions
    assert "10000003" not in st.positions


async def test_existing_position_is_managed_not_reopened():
    # 开仓均价 99.2：默认 0.4% 止盈止损区间约为 [98.80, 99.60]，当前价 99 在区间内
    st = make_strategy(positions={"10000003": _sol_position(entry_price=99.2)})
    st.contract_ids["SOL-USDT"] = "10000003"
    set_prices(st, "SOL-USDT", _long_signal_history())
    await st._update_account_info()

    await st._execute_strategy_for_symbol("SOL-USDT")
    # 已有同向多仓、价格未触发止盈止损 -> 不应再开仓
    st.client.place_order.assert_not_awaited()


async def test_failed_account_refresh_pauses_trading():
    st = make_strategy()
    st.client.get_account_info = AsyncMock(side_effect=RuntimeError("network down"))
    assert await st._refresh_account_if_needed() is False
    assert st._account_dirty is True
