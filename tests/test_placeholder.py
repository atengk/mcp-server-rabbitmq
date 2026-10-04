"""工程骨架与元数据自动化测试用例.

@author Ateng
@since 2026-10-04
"""

from mcp_server_rabbitmq import __version__


def test_version() -> None:
    """验证项目基础版本号配置正确."""
    assert __version__ == "0.1.0"
