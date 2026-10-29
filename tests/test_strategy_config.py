"""策略参数必须来自 Config（.env），而不是硬编码"""

from decimal import Decimal

from tests.helpers import make_config, make_strategy


def test_strategy_uses_configured_risk_parameters():
    cfg = make_config(leverage=3, take_profit_pct=0.01, stop_loss_pct=0.02,
                      base_position_size=0.1, min_trade_interval=9000)
    st = make_strategy(cfg)
    sc = st.strategy_config
    assert sc.leverage == 3
    assert sc.take_profit_pct == Decimal("0.01")
    assert sc.stop_loss_pct == Decimal("0.02")
    assert sc.base_position_size == Decimal("0.1")
    assert st.min_trade_interval == 9000


def test_defaults_unchanged_when_config_uses_defaults():
    sc = make_strategy(make_config()).strategy_config
    assert sc.leverage == 50
    assert sc.take_profit_pct == Decimal("0.004")
    assert sc.stop_loss_pct == Decimal("0.004")
    assert sc.base_position_size == Decimal("0.05")
