"""止盈止损必须对交易所同步回来的持仓生效"""

import pytest

from edgex_types import OrderSide, Position, TradeDirection
from tests.helpers import make_config, make_strategy, price


def _position(direction, entry=100.0):
    # 交易所返回的持仓没有止盈止损价（edgex_client 中固定为 0）
    return Position(symbol="10000003", direction=direction, size=2.0, entry_price=entry,
                    stop_loss=0.0, take_profit=0.0, leverage=50, opening_time=0)


@pytest.mark.parametrize(
    "direction, last_price, close_side",
    [
        (TradeDirection.LONG, 98.9, OrderSide.SELL),    # 多单止损（-1.1% < -1%）
        (TradeDirection.LONG, 102.1, OrderSide.SELL),   # 多单止盈（+2.1% > +2%）
        (TradeDirection.SHORT, 101.1, OrderSide.BUY),   # 空单止损
        (TradeDirection.SHORT, 97.9, OrderSide.BUY),    # 空单止盈
    ],
)
async def test_exits_trigger_on_exchange_positions(direction, last_price, close_side):
    cfg = make_config(stop_loss_pct=0.01, take_profit_pct=0.02)
    st = make_strategy(cfg, positions={"10000003": _position(direction)})
    st.contract_ids["SOL-USDT"] = "10000003"
    await st._update_account_info()
    # 价格平稳后突变，均线偏离不会单独触发反向信号的情况也要能止损
    st.price_history["SOL-USDT"] = [price(last_price)] * 5

    await st._execute_strategy_for_symbol("SOL-USDT")

    st.client.place_order.assert_awaited_once()
    order = st.client.place_order.await_args.args[0]
    assert order.side == close_side
    assert order.quantity == 2.0
    assert "SOL-USDT" not in st.positions


async def test_no_exit_inside_band():
    cfg = make_config(stop_loss_pct=0.01, take_profit_pct=0.02)
    st = make_strategy(cfg, positions={"10000003": _position(TradeDirection.LONG)})
    st.contract_ids["SOL-USDT"] = "10000003"
    await st._update_account_info()
    st.price_history["SOL-USDT"] = [price(100.5)] * 5

    await st._execute_strategy_for_symbol("SOL-USDT")
    st.client.place_order.assert_not_awaited()


async def test_default_exit_prices_from_entry():
    cfg = make_config(stop_loss_pct=0.01, take_profit_pct=0.02)
    st = make_strategy(cfg, positions={"10000003": _position(TradeDirection.SHORT, entry=200.0)})
    st.contract_ids["SOL-USDT"] = "10000003"
    await st._update_account_info()
    pos = st.positions["SOL-USDT"]
    assert pos.stop_loss == pytest.approx(202.0)
    assert pos.take_profit == pytest.approx(196.0)
