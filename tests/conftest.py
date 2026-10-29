"""
离线单元测试公共配置

所有测试都不访问网络、不使用真实密钥：交易所客户端一律用 mock 替换。
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    """兜底：任何测试意外发起 HTTP/WebSocket 连接都会立即失败，而不是访问真实交易所"""
    import aiohttp
    import requests
    import websocket

    def _blocked(*args, **kwargs):
        raise RuntimeError("测试中禁止访问网络")

    async def _blocked_async(*args, **kwargs):
        _blocked()

    monkeypatch.setattr(aiohttp.ClientSession, "_request", _blocked_async)
    monkeypatch.setattr(requests.Session, "request", _blocked)
    monkeypatch.setattr(websocket, "create_connection", _blocked)
