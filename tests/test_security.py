"""安全写保护门禁与高危动作二次确认单元测试.

@author Ateng
@since 2026-10-04
"""

import pytest

from mcp_server_rabbitmq.core.config import RabbitMQServerConfig, set_global_config
from mcp_server_rabbitmq.core.security import (
    WriteGateError,
    check_confirmation,
    check_write_permission,
    require_write,
)


class TestWriteGate:
    """测试只读保护门禁 (Write Gate)."""

    def test_write_blocked_when_allow_write_false(self) -> None:
        """测试在默认只读模式下阻止写入操作."""
        cfg = RabbitMQServerConfig(allow_write=False)
        with pytest.raises(WriteGateError) as exc_info:
            check_write_permission("declare_queue", config=cfg)

        assert "写入保护门禁已启用" in str(exc_info.value)
        assert "declare_queue" in str(exc_info.value)

    def test_write_allowed_when_allow_write_true(self) -> None:
        """测试在显式开启允许写入时放行操作."""
        cfg = RabbitMQServerConfig(allow_write=True)
        # 应正常返回，不抛出任何异常
        check_write_permission("declare_exchange", config=cfg)

    def test_sync_function_decorator_blocks_write(self) -> None:
        """测试同步函数装饰器拦截."""
        set_global_config(RabbitMQServerConfig(allow_write=False))

        @require_write("publish_message")
        def do_publish() -> str:
            return "success"

        with pytest.raises(WriteGateError):
            do_publish()

    def test_sync_function_decorator_allows_write(self) -> None:
        """测试同步函数装饰器放行."""
        set_global_config(RabbitMQServerConfig(allow_write=True))

        @require_write("publish_message")
        def do_publish() -> str:
            return "success"

        assert do_publish() == "success"

    @pytest.mark.asyncio
    async def test_async_function_decorator_blocks_write(self) -> None:
        """测试异步函数装饰器拦截."""
        set_global_config(RabbitMQServerConfig(allow_write=False))

        @require_write("delete_exchange")
        async def do_delete() -> str:
            return "deleted"

        with pytest.raises(WriteGateError):
            await do_delete()

    @pytest.mark.asyncio
    async def test_async_function_decorator_allows_write(self) -> None:
        """测试异步函数装饰器放行."""
        set_global_config(RabbitMQServerConfig(allow_write=True))

        @require_write("delete_exchange")
        async def do_delete() -> str:
            return "deleted"

        assert await do_delete() == "deleted"


class TestDoubleConfirmation:
    """测试高危动作二次确认守卫."""

    def test_confirmation_needed_when_confirm_false(self) -> None:
        """测试未传入 confirm=True 时拦截并返回预估影响报告."""
        report = check_confirmation(
            action="purge_queue",
            confirm=False,
            target="order_queue",
            impact_estimate="预估清空队列中 100 条待处理消息",
        )
        assert report is not None
        assert report["status"] == "requires_confirmation"
        assert report["confirmed"] is False
        assert report["action"] == "purge_queue"
        assert report["target"] == "order_queue"
        assert "预估清空队列中 100 条待处理消息" in report["impact_estimate"]

    def test_confirmation_passed_when_confirm_true(self) -> None:
        """测试传入 confirm=True 时放行返回 None."""
        report = check_confirmation(
            action="purge_queue",
            confirm=True,
            target="order_queue",
        )
        assert report is None
