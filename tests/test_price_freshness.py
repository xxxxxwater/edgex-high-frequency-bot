"""价格过期时必须改用 REST ticker，不能用冻结的价格做交易/止损判断"""

from unittest.mock import AsyncMock

from edgex_types import OrderSide, Position, TradeDirection
from tests.helpers import make_config, make_strategy, price, set_prices


def _with_clock(st, start=1_000_000):
    clock = {"now": start}
    st._now_ms = lambda: clock["now"]
    return clock


def _ticker_sequence(st, prices):
    it = iter(prices)
    st.client.get_ticker = AsyncMock(side_effect=lambda cid: {"lastPrice": str(next(it))})


async def test_without_websocket_every_loop_uses_fresh_rest_price():
    # 之前凑满 5 条价格后就不再请求 REST，价格永久停在第 5 条
    st = make_strategy()
    st.contract_ids["SOL-USDT"] = "10000003"
    clock = _with_clock(st)
    _ticker_sequence(st, [100.0 + i for i in range(10)])

    for _ in range(10):
        await st._execute_strategy_for_symbol("SOL-USDT")
        clock["now"] += 1000

    assert st.client.get_ticker.await_count == 10
    assert st.price_history["SOL-USDT"][-1].close == 109.0


async def test_fresh_websocket_price_skips_rest():
    st = make_strategy()
    st.contract_ids["SOL-USDT"] = "10000003"
    _with_clock(st)
    set_prices(st, "SOL-USDT", [price(100)] * 5)

    await st._execute_strategy_for_symbol("SOL-USDT")
    st.client.get_ticker.assert_not_awaited()


async def test_websocket_callback_marks_price_fresh():
    st = make_strategy()
    _with_clock(st)
    st._on_price_update("SOL-USDT", price(100))
    assert st._ws_price_is_fresh("SOL-USDT")
    assert not st._ws_price_is_fresh("BTC-USDT")


async def test_stop_loss_uses_rest_price_after_websocket_goes_silent():
    position = Position(symbol="10000003", direction=TradeDirection.LONG, size=2.0, entry_price=100.0,
                        stop_loss=0.0, take_profit=0.0, leverage=50, opening_time=0)
    st = make_strategy(make_config(stop_loss_pct=0.01, take_profit_pct=0.02), positions={"10000003": position})
    st.contract_ids["SOL-USDT"] = "10000003"
    clock = _with_clock(st)
    await st._update_account_info()
    set_prices(st, "SOL-USDT", [price(100)] * 5)  # 最后一次 WebSocket 推送

    clock["now"] += st.max_ws_price_age_ms + 1000  # 之后 WebSocket 没有任何推送
    _ticker_sequence(st, [98.0])                    # 实际价格已跌破 1% 止损
    await st._execute_strategy_for_symbol("SOL-USDT")

    st.client.place_order.assert_awaited_once()
    assert st.client.place_order.await_args.args[0].side == OrderSide.SELL


async def test_failed_or_timed_out_open_order_still_enters_cooldown():
    # 超时的订单可能已被交易所接受；立即重试会重复开仓
    st = make_strategy()
    st.contract_ids["SOL-USDT"] = "10000003"
    clock = _with_clock(st)
    await st._update_account_info()
    st.client.place_order = AsyncMock(side_effect=TimeoutError("request timed out"))

    for _ in range(3):
        set_prices(st, "SOL-USDT", [price(100)] * 4 + [price(99)])  # 持续做多信号
        assert await st._refresh_account_if_needed()
        await st._execute_strategy_for_symbol("SOL-USDT")
        clock["now"] += 1000

    assert st.client.place_order.await_count == 1
