"""WebSocket ticker 必须按合约分发到正确的交易对"""

import json

import pytest

from websocket_client import RealTimePriceStream

CONTRACTS = {"BTC-USDT": "10000001", "SOL-USDT": "10000003"}


@pytest.fixture
def stream():
    s = RealTimePriceStream(symbols=list(CONTRACTS), contract_ids=dict(CONTRACTS),
                            base_url="wss://example.invalid", account_id=0, stark_private_key="")
    s.received = []
    s.add_price_callback(lambda sym, p: s.received.append((sym, p.close)))
    return s


def _msg(contract_id, last_price, nested=True):
    item = {"contractId": contract_id, "lastPrice": str(last_price)}
    if nested:
        return json.dumps({"type": "quote-event", "channel": f"ticker.{contract_id}",
                           "content": {"dataType": "Snapshot", "data": [item]}})
    return json.dumps({"type": "quote-event", "channel": f"ticker.{contract_id}", "data": item})


def test_sdk_keeps_only_one_ticker_handler(stream):
    # 复现根因：SDK 对同一消息类型只保留最后注册的 handler
    client = stream.ws_manager.get_public_client()
    client.on_message("ticker", lambda m: "BTC")
    client.on_message("ticker", lambda m: "SOL")
    assert client.handlers["ticker"]("") == "SOL"


@pytest.mark.parametrize("nested", [True, False])
def test_tickers_routed_by_contract(stream, nested):
    stream._dispatch_ticker_message(_msg("10000001", 65000.5, nested))
    stream._dispatch_ticker_message(_msg("10000003", 150.25, nested))
    assert stream.received == [("BTC-USDT", 65000.5), ("SOL-USDT", 150.25)]
    assert [p.close for p in stream.price_history["BTC-USDT"]] == [65000.5]
    assert [p.close for p in stream.price_history["SOL-USDT"]] == [150.25]


def test_routes_by_channel_when_contract_id_missing(stream):
    msg = json.dumps({"type": "quote-event", "channel": "ticker.10000003",
                      "content": {"data": [{"lastPrice": "151"}]}})
    stream._dispatch_ticker_message(msg)
    assert stream.received == [("SOL-USDT", 151.0)]


def test_unknown_contract_and_bad_messages_are_ignored(stream):
    stream._dispatch_ticker_message(_msg("99999999", 1.0))
    stream._dispatch_ticker_message("not json")
    stream._dispatch_ticker_message(_msg("10000001", 0))  # 无效价格
    assert stream.received == []


async def test_start_registers_dispatcher_for_all_symbols(stream, monkeypatch):
    import websocket_client
    client = stream.ws_manager.get_public_client()
    monkeypatch.setattr(stream.ws_manager, "connect_public", lambda: None)
    monkeypatch.setattr(client, "subscribe", lambda topic, params=None: True)

    async def _no_sleep(_):
        return None
    monkeypatch.setattr(websocket_client.asyncio, "sleep", _no_sleep)

    await stream.start()

    # 通过 SDK 实际保存的 handler 投递两个币种的消息
    handler = client.handlers["ticker"]
    handler(_msg("10000001", 65000.5))
    handler(_msg("10000003", 150.25))
    assert stream.received == [("BTC-USDT", 65000.5), ("SOL-USDT", 150.25)]
    assert len(client.on_disconnect_hooks) == 1
