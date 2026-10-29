"""配置归一化"""

import pytest

from config import load_config
from tests.helpers import make_config


@pytest.mark.parametrize("raw, expected", [
    ("0x" + "ab" * 32, "ab" * 32),
    ("0X" + "AB" * 32, "AB" * 32),
    ("  " + "ab" * 32 + "\n", "ab" * 32),
    ("1" * 63, "0" + "1" * 63),       # 奇数位补前导 0，数值不变
    ("", None),
])
def test_stark_private_key_is_normalized(raw, expected):
    assert make_config(stark_private_key=raw).stark_private_key == expected


def test_normalized_key_can_sign():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "sdk"))
    from edgex_sdk.internal.starkex_signing_adapter import StarkExSigningAdapter

    key = make_config(stark_private_key="0x" + "ab" * 32).stark_private_key
    r, s = StarkExSigningAdapter().sign(b"\x01" * 32, key)
    assert r and s


def test_symbols_are_stripped(monkeypatch):
    monkeypatch.setattr("config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("EDGEX_SYMBOLS", "BTC-USDT, ETH-USDT ,,SOL-USDT")
    assert load_config().symbols == ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
