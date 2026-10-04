"""Broker 探活与集群概览工具单元测试.

@author Ateng
@since 2026-10-04
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_server_rabbitmq.core.config import (
    RabbitMQConnectionConfig,
    RabbitMQServerConfig,
    set_global_config,
)
from mcp_server_rabbitmq.tools.broker import (
    rabbitmq_list_connections,
    rabbitmq_overview,
    rabbitmq_ping,
)


@pytest.fixture(autouse=True)
def setup_test_config() -> None:
    """初始化测试配置."""
    test_config = RabbitMQServerConfig(
        connections={
            "default": RabbitMQConnectionConfig(
                name="default",
                amqp_url="amqp://guest:secret@localhost:5672/",
                management_url=None,
            ),
            "with_mgmt": RabbitMQConnectionConfig(
                name="with_mgmt",
                amqp_url="amqp://admin:admin123@127.0.0.1:5672/vhost1",
                management_url="http://admin:admin123@127.0.0.1:15672/",
            ),
        }
    )
    set_global_config(test_config)


def test_rabbitmq_list_connections() -> None:
    """测试列出所有配置连接并确保凭据脱敏."""
    conns = rabbitmq_list_connections()
    assert len(conns) == 2
    names = [c["name"] for c in conns]
    assert "default" in names
    assert "with_mgmt" in names

    # 验证脱敏
    for c in conns:
        assert "secret" not in c["amqp_url"]
        assert "admin123" not in c["amqp_url"]
        assert "***" in c["amqp_url"]


@pytest.mark.asyncio
async def test_rabbitmq_ping_success() -> None:
    """测试 ping 测量 AMQP 往返延迟成功."""
    mock_channel = AsyncMock()
    mock_connection = AsyncMock()
    mock_connection.channel.return_value = mock_channel

    with patch("aio_pika.connect_robust", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_connection

        result = await rabbitmq_ping(connection="default")

        assert result["status"] == "ok"
        assert result["connection"] == "default"
        assert result["masked_url"] == "amqp://guest:***@localhost:5672/"
        assert isinstance(result["latency_ms"], float)
        assert result["latency_ms"] >= 0.0

        mock_connect.assert_called_once_with("amqp://guest:secret@localhost:5672/")
        mock_channel.close.assert_called_once()
        mock_connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_rabbitmq_ping_failure() -> None:
    """测试 ping 连接失败时返回脱敏错误信息."""
    with patch("aio_pika.connect_robust", side_effect=ConnectionRefusedError("Connection refused to 5672")):
        result = await rabbitmq_ping(connection="default")

        assert result["status"] == "error"
        assert result["connection"] == "default"
        assert result["masked_url"] == "amqp://guest:***@localhost:5672/"
        assert "Connection refused" in result["message"]


@pytest.mark.asyncio
async def test_rabbitmq_overview_degraded_when_no_mgmt_url() -> None:
    """测试未配置 Management API 时优雅降级 (ADR-0001)."""
    result = await rabbitmq_overview(connection="default")

    assert result["status"] == "degraded"
    assert result["connection"] == "default"
    assert "未配置 RabbitMQ Management API" in result["message"]
    assert result["management_url"] is None


@pytest.mark.asyncio
async def test_rabbitmq_overview_success() -> None:
    """测试调用 Management API 成功获取集群指标."""
    mock_payload = {
        "cluster_name": "rabbit@node-cluster",
        "rabbitmq_version": "3.13.2",
        "erlang_version": "26.2.5",
        "node": "rabbit@node1",
        "queue_totals": {"messages": 42, "messages_ready": 40, "messages_unacknowledged": 2},
        "object_totals": {"queues": 5, "exchanges": 7, "connections": 3, "channels": 4},
    }

    mock_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/overview"),
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        result = await rabbitmq_overview(connection="with_mgmt")

        assert result["status"] == "ok"
        assert result["connection"] == "with_mgmt"
        assert result["cluster_name"] == "rabbit@node-cluster"
        assert result["rabbitmq_version"] == "3.13.2"
        assert result["erlang_version"] == "26.2.5"
        assert result["queue_totals"]["messages"] == 42
        assert result["object_totals"]["queues"] == 5


@pytest.mark.asyncio
async def test_rabbitmq_overview_http_error() -> None:
    """测试 Management API 请求失败时的错误处理."""
    mock_response = httpx.Response(
        status_code=401,
        content=b"Unauthorized",
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/overview"),
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        result = await rabbitmq_overview(connection="with_mgmt")

        assert result["status"] == "error"
        assert result["connection"] == "with_mgmt"
        assert "401" in result["message"]


@pytest.mark.asyncio
async def test_rabbitmq_overview_url_path_joining() -> None:
    """测试各种格式的 Management API 基地址路径拼接均能得到规范的 /api/overview."""
    mock_payload = {"status": "ok"}
    mock_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/overview"),
    )

    cases = [
        "http://admin:pwd@127.0.0.1:15672",
        "http://admin:pwd@127.0.0.1:15672/",
        "http://admin:pwd@127.0.0.1:15672/api",
        "http://admin:pwd@127.0.0.1:15672/api/",
    ]

    for idx, base_url in enumerate(cases):
        name = f"c_{idx}"
        cfg = RabbitMQServerConfig(
            connections={
                name: RabbitMQConnectionConfig(
                    name=name,
                    amqp_url="amqp://localhost:5672/",
                    management_url=base_url,
                )
            }
        )
        set_global_config(cfg)

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response) as mock_get:
            await rabbitmq_overview(connection=name)
            mock_get.assert_called_once_with("http://admin:pwd@127.0.0.1:15672/api/overview")


@pytest.mark.asyncio
async def test_rabbitmq_ping_logs_masked_credentials(caplog: pytest.LogCaptureFixture) -> None:
    """测试 ping 失败日志中明文密码被替换为 ***，杜绝日志泄露."""
    leak_err = ConnectionRefusedError(
        "failed to connect to amqp://user:top_secret_123@127.0.0.1:5672/"
    )
    with patch("aio_pika.connect_robust", side_effect=leak_err):
        await rabbitmq_ping(connection="default")

        assert "top_secret_123" not in caplog.text
        assert "***" in caplog.text
