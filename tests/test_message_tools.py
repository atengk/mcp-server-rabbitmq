"""RabbitMQ 消息发布、无损采样 (Peek) 与受控消费单元测试.

@author Ateng
@since 2026-10-04
"""

import base64
from unittest.mock import AsyncMock, patch

import pytest
from aio_pika import Message

from mcp_server_rabbitmq.core.config import (
    RabbitMQConnectionConfig,
    RabbitMQServerConfig,
    set_global_config,
)
from mcp_server_rabbitmq.core.security import WriteGateError
from mcp_server_rabbitmq.tools.messages import (
    rabbitmq_get_messages,
    rabbitmq_peek_messages,
    rabbitmq_publish_message,
)


@pytest.fixture(autouse=True)
def setup_message_config() -> None:
    """初始化消息收发测试配置."""
    cfg = RabbitMQServerConfig(
        allow_write=True,
        connections={
            "default": RabbitMQConnectionConfig(
                name="default",
                amqp_url="amqp://guest:guest@127.0.0.1:5672/",
            ),
        },
    )
    set_global_config(cfg)


class TestMessagePublishing:
    """消息发布工具单元测试."""

    @pytest.mark.asyncio
    async def test_publish_dict_payload_json_serialization(self) -> None:
        """测试字典载荷自动 JSON 序列化并默认持久化 (delivery_mode=2)."""
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.get_exchange.return_value = mock_exchange
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            payload = {"order_id": "ORD-12345", "amount": 99.8}
            res = await rabbitmq_publish_message(
                exchange="orders_exchange",
                routing_key="orders.created",
                payload=payload,
            )

            assert res["status"] == "ok"
            assert res["exchange"] == "orders_exchange"
            assert res["routing_key"] == "orders.created"
            assert res["content_type"] == "application/json"
            assert res["payload_size"] > 0

            # 验证底层 exchange.publish 调用入参
            mock_exchange.publish.assert_called_once()
            call_args = mock_exchange.publish.call_args
            msg_arg: Message = call_args[0][0]
            routing_key_arg = call_args[1]["routing_key"]
            assert routing_key_arg == "orders.created"
            assert msg_arg.content_type == "application/json"
            assert msg_arg.delivery_mode.value == 2
            assert b"ORD-12345" in msg_arg.body

    @pytest.mark.asyncio
    async def test_publish_string_payload(self) -> None:
        """测试纯字符串消息发布."""
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.get_exchange.return_value = mock_exchange
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_publish_message(
                exchange="logs_exchange",
                routing_key="sys.info",
                payload="system boot successfully",
            )
            assert res["status"] == "ok"
            assert res["content_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_publish_blocked_by_write_gate(self) -> None:
        """测试在只读模式 (allow_write=False) 下消息发布被写门禁拦截."""
        set_global_config(RabbitMQServerConfig(allow_write=False))
        with pytest.raises(WriteGateError) as exc_info:
            await rabbitmq_publish_message("ex", "rk", "hello")
        assert "写入保护门禁已启用" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_publish_with_headers_and_priority(self) -> None:
        """测试自定义 headers 与 priority 组装."""
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.get_exchange.return_value = mock_exchange
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            headers = {"x-trace-id": "trace-999"}
            await rabbitmq_publish_message(
                exchange="test_ex",
                routing_key="rk",
                payload="data",
                priority=5,
                headers=headers,
                expiration=30000,
            )
            mock_exchange.publish.assert_called_once()
            msg_arg: Message = mock_exchange.publish.call_args[0][0]
            assert msg_arg.priority == 5
            assert msg_arg.headers == headers
            assert msg_arg.expiration == 30.0


class TestMessagePeeking:
    """零损探查无损采样 (Peek) 单元测试."""

    @pytest.mark.asyncio
    async def test_peek_messages_always_requeues(self) -> None:
        """测试采样读取队列后必定调用 reject(requeue=True) 绝不调用 ack (ADR-0002)."""
        mock_msg = AsyncMock()
        mock_msg.body = b'{"event": "ping"}'
        mock_msg.content_type = "application/json"
        mock_msg.message_id = "msg-001"
        mock_msg.delivery_mode = 2
        mock_msg.priority = 0
        mock_msg.headers = {}
        mock_msg.routing_key = "test.rk"
        mock_msg.exchange = "test.ex"
        mock_msg.redelivered = False

        mock_queue = AsyncMock()
        # 第一次返回消息，第二次返回 None
        mock_queue.get.side_effect = [mock_msg, None]
        mock_channel = AsyncMock()
        mock_channel.get_queue.return_value = mock_queue
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_peek_messages(queue="tasks_queue", count=5)

            assert res["status"] == "ok"
            assert res["queue"] == "tasks_queue"
            assert res["count"] == 1
            assert res["peeked"] is True
            assert len(res["messages"]) == 1
            assert res["messages"][0]["payload"] == {"event": "ping"}

            # 验证核心安全防御：必定 reject(requeue=True)，严禁 ack
            mock_msg.reject.assert_called_once_with(requeue=True)
            mock_msg.ack.assert_not_called()

    @pytest.mark.asyncio
    async def test_peek_empty_queue(self) -> None:
        """测试空队列时安全返回空列表."""
        mock_queue = AsyncMock()
        mock_queue.get.return_value = None
        mock_channel = AsyncMock()
        mock_channel.get_queue.return_value = mock_queue
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_peek_messages(queue="empty_queue", count=5)
            assert res["status"] == "ok"
            assert res["count"] == 0
            assert res["messages"] == []


class TestMessageConsumption:
    """受控消费与拉取工具单元测试."""

    @pytest.mark.asyncio
    async def test_get_messages_default_ack_false_requeues(self) -> None:
        """测试默认 ack=False 时不删除消息，安全 Requeue."""
        mock_msg = AsyncMock()
        mock_msg.body = b"hello task"
        mock_msg.content_type = "text/plain"
        mock_msg.message_id = "msg-101"
        mock_msg.delivery_mode = 2
        mock_msg.priority = 0
        mock_msg.headers = {}
        mock_msg.routing_key = "rk"
        mock_msg.exchange = ""
        mock_msg.redelivered = False

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [mock_msg, None]
        mock_channel = AsyncMock()
        mock_channel.get_queue.return_value = mock_queue
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_get_messages(queue="tasks_queue", count=1, ack=False)
            assert res["status"] == "ok"
            assert res["acknowledged"] is False
            assert res["messages"][0]["payload"] == "hello task"

            mock_msg.reject.assert_called_once_with(requeue=True)
            mock_msg.ack.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_messages_ack_true_calls_ack(self) -> None:
        """测试显式传入 ack=True 时物理确认出队."""
        mock_msg = AsyncMock()
        mock_msg.body = b"hello task"
        mock_msg.content_type = "text/plain"
        mock_msg.message_id = "msg-102"
        mock_msg.delivery_mode = 2
        mock_msg.priority = 0
        mock_msg.headers = {}
        mock_msg.routing_key = "rk"
        mock_msg.exchange = ""
        mock_msg.redelivered = False

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [mock_msg, None]
        mock_channel = AsyncMock()
        mock_channel.get_queue.return_value = mock_queue
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_get_messages(queue="tasks_queue", count=1, ack=True)
            assert res["status"] == "ok"
            assert res["acknowledged"] is True

            mock_msg.ack.assert_called_once()
            mock_msg.reject.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_messages_ack_true_blocked_when_readonly(self) -> None:
        """测试在只读保护模式下，若请求 ack=True 物理确认出队会被写门禁拦截."""
        set_global_config(RabbitMQServerConfig(allow_write=False))
        with pytest.raises(WriteGateError) as exc_info:
            await rabbitmq_get_messages(queue="tasks_queue", count=1, ack=True)
        assert "写入保护门禁已启用" in str(exc_info.value)


class TestBinaryPayloadSafety:
    """非 UTF-8 二进制载荷 Base64 安全回显单元测试."""

    @pytest.mark.asyncio
    async def test_binary_payload_base64_encoded(self) -> None:
        """测试包含非法 UTF-8 字节的二进制载荷安全转为 Base64，杜绝崩溃."""
        invalid_utf8 = b"\x80\xff\xfe\x00\x01\x02\x03"

        mock_msg = AsyncMock()
        mock_msg.body = invalid_utf8
        mock_msg.content_type = "application/octet-stream"
        mock_msg.message_id = "bin-msg-1"
        mock_msg.delivery_mode = 1
        mock_msg.priority = 0
        mock_msg.headers = {}
        mock_msg.routing_key = "bin.rk"
        mock_msg.exchange = ""
        mock_msg.redelivered = False

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [mock_msg, None]
        mock_channel = AsyncMock()
        mock_channel.get_queue.return_value = mock_queue
        mock_conn = AsyncMock()
        mock_conn.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_conn):
            res = await rabbitmq_peek_messages(queue="bin_queue", count=1)
            msg_info = res["messages"][0]
            assert msg_info["encoding"] == "base64"
            assert msg_info["payload"] == base64.b64encode(invalid_utf8).decode("ascii")
