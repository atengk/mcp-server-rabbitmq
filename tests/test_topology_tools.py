"""RabbitMQ 拓扑管理工具单元测试 (交换机、队列与绑定).

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
from mcp_server_rabbitmq.core.security import WriteGateError
from mcp_server_rabbitmq.tools.topology import (
    rabbitmq_bind_queue,
    rabbitmq_declare_exchange,
    rabbitmq_declare_queue,
    rabbitmq_delete_exchange,
    rabbitmq_delete_queue,
    rabbitmq_get_queue,
    rabbitmq_list_bindings,
    rabbitmq_list_exchanges,
    rabbitmq_list_queues,
    rabbitmq_purge_queue,
    rabbitmq_unbind_queue,
)


@pytest.fixture(autouse=True)
def setup_topology_config() -> None:
    """初始化拓扑测试所需的只读与可写配置."""
    cfg = RabbitMQServerConfig(
        allow_write=True,
        connections={
            "default": RabbitMQConnectionConfig(
                name="default",
                amqp_url="amqp://guest:guest@127.0.0.1:5672/",
                management_url="http://guest:guest@127.0.0.1:15672/",
            ),
            "no_mgmt": RabbitMQConnectionConfig(
                name="no_mgmt",
                amqp_url="amqp://guest:guest@127.0.0.1:5672/",
                management_url=None,
            ),
        },
    )
    set_global_config(cfg)


class TestExchangeManagement:
    """交换机查询、声明与受控删除测试."""

    @pytest.mark.asyncio
    async def test_list_exchanges_success(self) -> None:
        """测试通过 Management API 成功查询交换机列表."""
        mock_data = [
            {"name": "amq.direct", "type": "direct", "durable": True, "vhost": "/"},
            {"name": "order_events", "type": "topic", "durable": True, "vhost": "/"},
        ]
        mock_resp = httpx.Response(
            status_code=200,
            json=mock_data,
            request=httpx.Request("GET", "http://127.0.0.1:15672/api/exchanges"),
        )
        with patch.object(httpx.AsyncClient, "get", return_value=mock_resp):
            res = await rabbitmq_list_exchanges(connection="default")
            assert res["status"] == "ok"
            assert len(res["exchanges"]) == 2
            assert res["exchanges"][1]["name"] == "order_events"

    @pytest.mark.asyncio
    async def test_list_exchanges_degraded_when_no_mgmt(self) -> None:
        """测试未配置 Management API 时优雅降级."""
        res = await rabbitmq_list_exchanges(connection="no_mgmt")
        assert res["status"] == "degraded"
        assert "未配置 RabbitMQ Management API" in res["message"]

    @pytest.mark.asyncio
    async def test_declare_exchange_blocked_by_write_gate(self) -> None:
        """测试写保护门禁拦截声明交换机."""
        set_global_config(RabbitMQServerConfig(allow_write=False))
        with pytest.raises(WriteGateError) as exc_info:
            await rabbitmq_declare_exchange("test_ex", type="direct")
        assert "写入保护门禁已启用" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_declare_exchange_success(self) -> None:
        """测试成功声明交换机."""
        mock_channel = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_declare_exchange("my_topic_ex", type="topic", durable=True)
            assert res["status"] == "ok"
            assert res["name"] == "my_topic_ex"
            assert res["type"] == "topic"
            mock_channel.declare_exchange.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_exchange_requires_confirmation(self) -> None:
        """测试未传入 confirm=True 时拦截并返回预估."""
        res = await rabbitmq_delete_exchange("my_topic_ex", confirm=False)
        assert res["status"] == "requires_confirmation"
        assert res["confirmed"] is False
        assert res["target"] == "my_topic_ex"

    @pytest.mark.asyncio
    async def test_delete_exchange_success_when_confirmed(self) -> None:
        """测试传入 confirm=True 时物理删除交换机."""
        mock_channel = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_delete_exchange("my_topic_ex", confirm=True)
            assert res["status"] == "ok"
            assert res["name"] == "my_topic_ex"
            mock_channel.exchange_delete.assert_called_once_with("my_topic_ex", if_unused=False)


class TestQueueManagement:
    """队列查询、单队列详情、声明、清空与删除测试."""

    @pytest.mark.asyncio
    async def test_list_queues_success(self) -> None:
        """测试成功查询队列列表与指标."""
        mock_data = [
            {
                "name": "payment_queue",
                "messages_ready": 10,
                "messages_unacknowledged": 2,
                "consumers": 1,
                "vhost": "/",
            }
        ]
        mock_resp = httpx.Response(
            status_code=200,
            json=mock_data,
            request=httpx.Request("GET", "http://127.0.0.1:15672/api/queues"),
        )
        with patch.object(httpx.AsyncClient, "get", return_value=mock_resp):
            res = await rabbitmq_list_queues(connection="default")
            assert res["status"] == "ok"
            assert len(res["queues"]) == 1
            assert res["queues"][0]["name"] == "payment_queue"

    @pytest.mark.asyncio
    async def test_get_queue_success(self) -> None:
        """测试获取单个队列元数据与高级属性."""
        mock_data = {
            "name": "payment_queue",
            "messages": 12,
            "arguments": {"x-dead-letter-exchange": "dlx_exchange", "x-message-ttl": 60000},
        }
        mock_resp = httpx.Response(
            status_code=200,
            json=mock_data,
            request=httpx.Request("GET", "http://127.0.0.1:15672/api/queues/%2F/payment_queue"),
        )
        with patch.object(httpx.AsyncClient, "get", return_value=mock_resp):
            res = await rabbitmq_get_queue("payment_queue", connection="default")
            assert res["status"] == "ok"
            assert res["queue"]["name"] == "payment_queue"
            assert res["queue"]["arguments"]["x-dead-letter-exchange"] == "dlx_exchange"

    @pytest.mark.asyncio
    async def test_declare_queue_blocked_by_write_gate(self) -> None:
        """测试写保护门禁拦截声明队列."""
        set_global_config(RabbitMQServerConfig(allow_write=False))
        with pytest.raises(WriteGateError):
            await rabbitmq_declare_queue("my_test_queue")

    @pytest.mark.asyncio
    async def test_declare_queue_with_dlx_and_ttl(self) -> None:
        """测试声明包含死信路由与 TTL 参数的规范队列."""
        mock_channel = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            args = {"x-dead-letter-exchange": "dlx_ex", "x-message-ttl": 10000}
            res = await rabbitmq_declare_queue("order_queue", durable=True, arguments=args)
            assert res["status"] == "ok"
            assert res["name"] == "order_queue"
            mock_channel.declare_queue.assert_called_once_with(
                "order_queue",
                durable=True,
                exclusive=False,
                auto_delete=False,
                arguments=args,
            )

    @pytest.mark.asyncio
    async def test_purge_queue_requires_confirmation(self) -> None:
        """测试清空队列未确认时防御拦截."""
        res = await rabbitmq_purge_queue("order_queue", confirm=False)
        assert res["status"] == "requires_confirmation"
        assert res["confirmed"] is False
        assert res["target"] == "order_queue"

    @pytest.mark.asyncio
    async def test_purge_queue_success_when_confirmed(self) -> None:
        """测试清空队列已确认时执行物理清空并返回条数."""
        mock_queue = AsyncMock()
        mock_queue.purge.return_value = 15
        mock_channel = AsyncMock()
        mock_channel.get_queue.return_value = mock_queue
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_purge_queue("order_queue", confirm=True)
            assert res["status"] == "ok"
            assert res["purged_count"] == 15
            mock_queue.purge.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_queue_requires_confirmation(self) -> None:
        """测试删除队列未确认时防御拦截."""
        res = await rabbitmq_delete_queue("order_queue", confirm=False)
        assert res["status"] == "requires_confirmation"
        assert res["confirmed"] is False

    @pytest.mark.asyncio
    async def test_delete_queue_success_when_confirmed(self) -> None:
        """测试删除队列已确认时执行物理删除."""
        mock_channel = AsyncMock()
        mock_channel.queue_delete.return_value = 8
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_delete_queue("order_queue", confirm=True)
            assert res["status"] == "ok"
            assert res["message_count"] == 8
            mock_channel.queue_delete.assert_called_once_with(
                "order_queue", if_unused=False, if_empty=False
            )


class TestBindingManagement:
    """路由绑定查询、绑定与解绑测试."""

    @pytest.mark.asyncio
    async def test_list_bindings_success(self) -> None:
        """测试查询绑定关系列表."""
        mock_data = [
            {
                "source": "order_events",
                "vhost": "/",
                "destination": "payment_queue",
                "destination_type": "queue",
                "routing_key": "order.created",
                "arguments": {},
            }
        ]
        mock_resp = httpx.Response(
            status_code=200,
            json=mock_data,
            request=httpx.Request("GET", "http://127.0.0.1:15672/api/bindings"),
        )
        with patch.object(httpx.AsyncClient, "get", return_value=mock_resp):
            res = await rabbitmq_list_bindings(connection="default")
            assert res["status"] == "ok"
            assert len(res["bindings"]) == 1
            assert res["bindings"][0]["routing_key"] == "order.created"

    @pytest.mark.asyncio
    async def test_bind_queue_blocked_by_write_gate(self) -> None:
        """测试写门禁拦截队列绑定."""
        set_global_config(RabbitMQServerConfig(allow_write=False))
        with pytest.raises(WriteGateError):
            await rabbitmq_bind_queue("my_queue", "my_ex", "rk")

    @pytest.mark.asyncio
    async def test_bind_queue_success(self) -> None:
        """测试队列绑定成功."""
        mock_queue = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.get_queue.return_value = mock_queue
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_bind_queue("payment_queue", "order_events", "order.created")
            assert res["status"] == "ok"
            assert res["queue"] == "payment_queue"
            assert res["exchange"] == "order_events"
            assert res["routing_key"] == "order.created"
            mock_queue.bind.assert_called_once_with("order_events", routing_key="order.created", arguments=None)

    @pytest.mark.asyncio
    async def test_unbind_queue_blocked_by_write_gate(self) -> None:
        """测试写门禁拦截队列解绑."""
        set_global_config(RabbitMQServerConfig(allow_write=False))
        with pytest.raises(WriteGateError):
            await rabbitmq_unbind_queue("my_queue", "my_ex", "rk")

    @pytest.mark.asyncio
    async def test_unbind_queue_success(self) -> None:
        """测试队列解绑成功."""
        mock_queue = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.get_queue.return_value = mock_queue
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_unbind_queue("payment_queue", "order_events", "order.created")
            assert res["status"] == "ok"
            assert res["queue"] == "payment_queue"
            assert res["exchange"] == "order_events"
            assert res["routing_key"] == "order.created"
            mock_queue.unbind.assert_called_once_with("order_events", routing_key="order.created", arguments=None)
