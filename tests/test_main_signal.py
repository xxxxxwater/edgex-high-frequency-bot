"""main.TradingBot 信号处理测试"""

import signal
import warnings
from unittest.mock import MagicMock, patch

import main


def _make_bot():
    # 跳过 __init__（会读取 .env、配置日志、安装全局信号处理器）
    bot = main.TradingBot.__new__(main.TradingBot)
    bot.config = MagicMock()
    bot.strategy = MagicMock()
    bot.monitor = None
    bot.is_running = True
    bot._stop_requested = False
    return bot


def test_signal_handler_stops_strategy_synchronously():
    bot = _make_bot()
    installed = {}
    with patch.object(main.signal, "signal", side_effect=lambda sig, h: installed.__setitem__(sig, h)):
        bot._setup_signal_handlers()

    with warnings.catch_warnings():
        # 旧实现会产生 "coroutine ... was never awaited" 警告且策略不会停止
        warnings.simplefilter("error", RuntimeWarning)
        installed[signal.SIGTERM](signal.SIGTERM, None)

    bot.strategy.stop.assert_called_once_with()
    assert bot._stop_requested is True


async def test_run_exits_if_stop_requested_during_initialize():
    bot = _make_bot()

    async def fake_initialize():
        bot.request_stop()
        return True

    bot.initialize = fake_initialize
    bot.start = MagicMock(side_effect=AssertionError("不应启动策略"))
    await bot.run()
    bot.start.assert_not_called()
