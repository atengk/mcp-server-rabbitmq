"""客户端连接与活跃信道排障诊断工具单元测试.

@author Ateng
@since 2026-10-04
"""

from unittest.mock import patch

import httpx
import pytest

from mcp_server_rabbitmq.core.config import (
    RabbitMQConnectionConfig,
    RabbitMQServerConfig,
    set_global_config,
)
from mcp_server_rabbitmq.tools.diagnostics import (
    rabbitmq_list_channels,
    rabbitmq_list_client_connections,
)


@pytest.fixture(autouse=True)
def setup_test_config() -> None:
    """初始化诊断测试连接配置."""
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


@pytest.mark.asyncio
async def test_list_client_connections_degraded_when_no_mgmt_url() -> None:
    """测试未配置 Management API 时优雅降级."""
    result = await rabbitmq_list_client_connections(connection="default")

    assert result["status"] == "degraded"
    assert result["connection"] == "default"
    assert "未配置 RabbitMQ Management API" in result["message"]
    assert result["client_connections"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_list_client_connections_success_and_masked() -> None:
    """测试正常提取客户端连接指标并执行属性脱敏."""
    mock_connections_payload = [
        {
            "name": "127.0.0.1:58432 -> 127.0.0.1:5672",
            "node": "rabbit@node1",
            "host": "127.0.0.1",
            "port": 5672,
            "peer_host": "127.0.0.1",
            "peer_port": 58432,
            "protocol": "AMQP 0-9-1",
            "auth_mechanism": "PLAIN",
            "ssl": False,
            "user": "admin",
            "vhost": "vhost1",
            "state": "running",
            "channels": 3,
            "recv_oct": 10240,
            "send_oct": 20480,
            "recv_oct_details": {"rate": 100.5},
            "send_oct_details": {"rate": 200.5},
            "connected_at": 1700000000000,
            "client_properties": {
                "product": "aio-pika",
                "version": "9.4.0",
                "platform": "Python 3.12",
                "password": "super_secret_password",
                "amqp_dsn": "amqp://admin:super_secret_password@127.0.0.1:5672/vhost1",
                "connection_name": "order-service-producer",
            },
        },
        {
            "name": "127.0.0.1:58433 -> 127.0.0.1:5672",
            "node": "rabbit@node1",
            "host": "127.0.0.1",
            "port": 5672,
            "peer_host": "127.0.0.1",
            "peer_port": 58433,
            "protocol": "AMQP 0-9-1",
            "auth_mechanism": "PLAIN",
            "ssl": True,
            "user": "guest",
            "vhost": "/",
            "state": "running",
            "channels": 1,
            "recv_oct": 512,
            "send_oct": 1024,
            "recv_oct_details": {"rate": 5.0},
            "send_oct_details": {"rate": 10.0},
            "connected_at": 1700000001000,
            "client_properties": {
                "product": "Spring AMQP",
                "version": "3.1.0",
            },
        },
    ]

    mock_response = httpx.Response(
        status_code=200,
        json=mock_connections_payload,
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/connections"),
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        result = await rabbitmq_list_client_connections(connection="with_mgmt")

        assert result["status"] == "ok"
        assert result["connection"] == "with_mgmt"
        assert result["total"] == 2
        conns = result["client_connections"]
        assert len(conns) == 2

        # 检查第一个连接的性能指标提取
        c1 = conns[0]
        assert c1["name"] == "127.0.0.1:58432 -> 127.0.0.1:5672"
        assert c1["peer_host"] == "127.0.0.1"
        assert c1["peer_port"] == 58432
        assert c1["channels"] == 3
        assert c1["recv_oct"] == 10240
        assert c1["send_oct"] == 20480
        assert c1["recv_rate"] == 100.5
        assert c1["send_rate"] == 200.5

        # 验证敏感属性脱敏
        props1 = c1["client_properties"]
        assert props1["product"] == "aio-pika"
        assert props1["password"] == "***"
        assert "super_secret_password" not in props1["password"]
        assert "super_secret_password" not in props1["amqp_dsn"]
        assert "***" in props1["amqp_dsn"]


@pytest.mark.asyncio
async def test_list_client_connections_filter_by_vhost() -> None:
    """测试按 vhost 过滤客户端连接."""
    mock_connections_payload = [
        {
            "name": "127.0.0.1:58432 -> 127.0.0.1:5672",
            "vhost": "vhost1",
            "channels": 2,
            "client_properties": {},
        },
        {
            "name": "127.0.0.1:58433 -> 127.0.0.1:5672",
            "vhost": "vhost2",
            "channels": 1,
            "client_properties": {},
        },
    ]

    mock_response = httpx.Response(
        status_code=200,
        json=mock_connections_payload,
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/vhosts/vhost1/connections"),
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        result = await rabbitmq_list_client_connections(connection="with_mgmt", vhost="vhost1")

        assert result["status"] == "ok"
        assert result["total"] == 1
        assert len(result["client_connections"]) == 1
        assert result["client_connections"][0]["vhost"] == "vhost1"


@pytest.mark.asyncio
async def test_list_client_connections_error_handling() -> None:
    """测试 Management API 返回 500 或网络错误时的优雅容错."""
    mock_response = httpx.Response(
        status_code=500,
        content=b"Internal Server Error",
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/connections"),
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        result = await rabbitmq_list_client_connections(connection="with_mgmt")

        assert result["status"] == "error"
        assert result["total"] == 0
        assert result["client_connections"] == []
        assert "500" in result["message"]

    # 测试网络异常
    with patch.object(httpx.AsyncClient, "get", side_effect=httpx.ConnectError("Connection refused")):
        res_net = await rabbitmq_list_client_connections(connection="with_mgmt")
        assert res_net["status"] == "error"
        assert "ConnectError" in res_net["error"]
        assert "无法连通" in res_net["message"] or "连接" in res_net["message"]


@pytest.mark.asyncio
async def test_list_channels_degraded_when_no_mgmt_url() -> None:
    """测试未配置 Management API 时信道查询优雅降级."""
    result = await rabbitmq_list_channels(connection="default")

    assert result["status"] == "degraded"
    assert result["connection"] == "default"
    assert "未配置 RabbitMQ Management API" in result["message"]
    assert result["channels"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_list_channels_success() -> None:
    """测试正常查询活跃信道指标与积压诊断."""
    mock_channels_payload = [
        {
            "name": "127.0.0.1:58432 -> 127.0.0.1:5672 (1)",
            "number": 1,
            "node": "rabbit@node1",
            "user": "admin",
            "vhost": "vhost1",
            "connection_details": {
                "name": "127.0.0.1:58432 -> 127.0.0.1:5672",
                "peer_host": "127.0.0.1",
                "peer_port": 58432,
            },
            "state": "running",
            "messages_unacknowledged": 15,
            "messages_uncommitted": 0,
            "acks_uncommitted": 0,
            "prefetch_count": 20,
            "global_prefetch_count": 0,
            "consumer_count": 2,
            "message_stats": {
                "publish_details": {"rate": 50.0},
                "deliver_get_details": {"rate": 45.0},
                "ack_details": {"rate": 40.0},
            },
        },
        {
            "name": "127.0.0.1:58432 -> 127.0.0.1:5672 (2)",
            "number": 2,
            "node": "rabbit@node1",
            "user": "admin",
            "vhost": "vhost1",
            "connection_details": {
                "name": "127.0.0.1:58432 -> 127.0.0.1:5672",
                "peer_host": "127.0.0.1",
                "peer_port": 58432,
            },
            "state": "idle",
            "messages_unacknowledged": 0,
            "messages_uncommitted": 0,
            "acks_uncommitted": 0,
            "prefetch_count": 100,
            "global_prefetch_count": 0,
            "consumer_count": 1,
            "message_stats": {
                "publish_details": {"rate": 0.0},
                "deliver_get_details": {"rate": 0.0},
                "ack_details": {"rate": 0.0},
            },
        },
    ]

    mock_response = httpx.Response(
        status_code=200,
        json=mock_channels_payload,
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/channels"),
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        result = await rabbitmq_list_channels(connection="with_mgmt")

        assert result["status"] == "ok"
        assert result["connection"] == "with_mgmt"
        assert result["total"] == 2
        channels = result["channels"]
        assert len(channels) == 2

        ch1 = channels[0]
        assert ch1["name"] == "127.0.0.1:58432 -> 127.0.0.1:5672 (1)"
        assert ch1["number"] == 1
        assert ch1["connection_name"] == "127.0.0.1:58432 -> 127.0.0.1:5672"
        assert ch1["peer_host"] == "127.0.0.1"
        assert ch1["peer_port"] == 58432
        assert ch1["state"] == "running"
        assert ch1["messages_unacknowledged"] == 15
        assert ch1["prefetch_count"] == 20
        assert ch1["consumer_count"] == 2
        assert ch1["publish_rate"] == 50.0
        assert ch1["deliver_rate"] == 45.0
        assert ch1["ack_rate"] == 40.0


@pytest.mark.asyncio
async def test_list_channels_filter_by_connection_and_vhost() -> None:
    """测试按连接名和 vhost 过滤信道."""
    mock_channels_payload = [
        {
            "name": "conn1 (1)",
            "vhost": "vhost1",
            "connection_details": {"name": "conn1"},
            "messages_unacknowledged": 5,
        },
        {
            "name": "conn1 (2)",
            "vhost": "vhost2",
            "connection_details": {"name": "conn1"},
            "messages_unacknowledged": 0,
        },
        {
            "name": "conn2 (1)",
            "vhost": "vhost1",
            "connection_details": {"name": "conn2"},
            "messages_unacknowledged": 1,
        },
    ]

    mock_response = httpx.Response(
        status_code=200,
        json=mock_channels_payload,
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/connections/conn1/channels"),
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        # 仅按 connection 过滤
        res_conn = await rabbitmq_list_channels(
            connection="with_mgmt", connection_name="conn1"
        )
        assert res_conn["status"] == "ok"
        assert res_conn["total"] == 2
        assert all(c["connection_name"] == "conn1" for c in res_conn["channels"])

        # 同时按 connection 和 vhost 过滤
        res_both = await rabbitmq_list_channels(
            connection="with_mgmt", connection_name="conn1", vhost="vhost1"
        )
        assert res_both["status"] == "ok"
        assert res_both["total"] == 1
        assert res_both["channels"][0]["name"] == "conn1 (1)"


@pytest.mark.asyncio
async def test_list_channels_error_handling() -> None:
    """测试信道查询时的错误处理与优雅容错."""
    mock_response = httpx.Response(
        status_code=404,
        content=b"Not Found",
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/channels"),
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        result = await rabbitmq_list_channels(connection="with_mgmt")

        assert result["status"] == "error"
        assert result["channels"] == []
        assert result["total"] == 0
        assert "404" in result["message"]


@pytest.mark.asyncio
async def test_list_client_connections_null_field_resilience() -> None:
    """测试客户端连接 API 返回 null 统计字段时绝不抛出 AttributeError 异常."""
    mock_payload = [
        {
            "name": "127.0.0.1:1234 -> 127.0.0.1:5672",
            "recv_oct_details": None,
            "send_oct_details": None,
            "client_properties": None,
        }
    ]
    mock_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/connections"),
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        result = await rabbitmq_list_client_connections(connection="with_mgmt")

        assert result["status"] == "ok"
        assert result["total"] == 1
        item = result["client_connections"][0]
        assert item["recv_rate"] == 0.0
        assert item["send_rate"] == 0.0
        assert item["client_properties"] == {}


@pytest.mark.asyncio
async def test_list_channels_null_field_resilience() -> None:
    """测试信道 API 返回 null 统计字典时绝不抛出 AttributeError 异常."""
    mock_payload = [
        {
            "name": "conn (1)",
            "connection_details": None,
            "message_stats": None,
        }
    ]
    mock_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "http://127.0.0.1:15672/api/channels"),
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        result = await rabbitmq_list_channels(connection="with_mgmt")

        assert result["status"] == "ok"
        assert result["total"] == 1
        ch = result["channels"][0]
        assert ch["publish_rate"] == 0.0
        assert ch["deliver_rate"] == 0.0
        assert ch["ack_rate"] == 0.0
        assert ch["connection_name"] is None
        assert ch["peer_host"] is None
