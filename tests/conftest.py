"""
离线单元测试公共配置

所有测试都不访问网络、不使用真实密钥：交易所客户端一律用 mock 替换。
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
