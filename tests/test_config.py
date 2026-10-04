"""配置中心与凭据脱敏单元测试.

@author Ateng
@since 2026-10-04
"""

from pathlib import Path

import pytest

from mcp_server_rabbitmq.core.config import (
    RabbitMQConnectionConfig,
    RabbitMQServerConfig,
    get_global_config,
    load_config,
    mask_url,
    reset_global_config,
    set_global_config,
)


class TestMaskUrl:
    """测试 URL 脱敏工具函数 mask_url."""

    def test_mask_standard_amqp_url(self) -> None:
        """测试标准 AMQP 密码脱敏."""
        raw = "amqp://guest:secret123@localhost:5672/my_vhost"
        expected = "amqp://guest:***@localhost:5672/my_vhost"
        assert mask_url(raw) == expected

    def test_mask_http_management_url(self) -> None:
        """测试 HTTP Management API 密码脱敏."""
        raw = "http://admin:P@ssw0rd!@127.0.0.1:15672/api/"
        expected = "http://admin:***@127.0.0.1:15672/api/"
        assert mask_url(raw) == expected

    def test_mask_url_without_password(self) -> None:
        """测试无密码 URL 保持原样."""
        raw = "amqp://localhost:5672/"
        assert mask_url(raw) == raw

    def test_mask_url_with_user_only(self) -> None:
        """测试仅包含用户名无密码的 URL."""
        raw = "amqp://guest@localhost:5672/"
        assert mask_url(raw) == raw

    def test_mask_none_or_empty_url(self) -> None:
        """测试 None 与空字符串安全防御."""
        assert mask_url(None) is None
        assert mask_url("") == ""

    def test_mask_malformed_url_fallback(self) -> None:
        """测试非标准畸形 URL 优雅容错降级."""
        raw = "not-a-valid-url"
        assert mask_url(raw) == raw

    def test_mask_text_with_embedded_url(self) -> None:
        """测试包含在复杂错误文本中的 URL 密码脱敏."""
        err_text = (
            "ConnectionRefusedError: failed to connect to "
            "amqp://guest:secret123@localhost:5672/vhost on port 5672"
        )
        masked = mask_url(err_text)
        assert "secret123" not in str(masked)
        assert "amqp://guest:***@localhost:5672/vhost" in str(masked)


class TestConfigLoading:
    """测试配置加载器 load_config 与数据模型."""

    def test_default_env_loading(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试无任何配置时回退到默认环境变量配置."""
        monkeypatch.delenv("MCP_RABBITMQ_URL", raising=False)
        monkeypatch.delenv("MCP_RABBITMQ_MANAGEMENT_URL", raising=False)
        monkeypatch.delenv("MCP_RABBITMQ_ALLOW_WRITE", raising=False)
        monkeypatch.delenv("MCP_RABBITMQ_CONFIG_PATH", raising=False)

        config = load_config()
        assert config.allow_write is False
        assert "default" in config.connections
        default_conn = config.get_connection("default")
        assert default_conn.amqp_url == "amqp://guest:guest@localhost:5672/"
        assert default_conn.management_url is None
        assert default_conn.masked_amqp_url == "amqp://guest:***@localhost:5672/"
        assert default_conn.masked_management_url is None

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试通过环境变量自定义配置."""
        monkeypatch.setenv("MCP_RABBITMQ_URL", "amqp://app:prod_pass@broker.example.com:5672/app_vhost")
        monkeypatch.setenv("MCP_RABBITMQ_MANAGEMENT_URL", "https://app:mgmt_pass@broker.example.com:15672/")
        monkeypatch.setenv("MCP_RABBITMQ_ALLOW_WRITE", "true")

        config = load_config()
        assert config.allow_write is True
        default_conn = config.get_connection("default")
        assert default_conn.amqp_url == "amqp://app:prod_pass@broker.example.com:5672/app_vhost"
        assert default_conn.masked_amqp_url == "amqp://app:***@broker.example.com:5672/app_vhost"
        assert default_conn.masked_management_url == "https://app:***@broker.example.com:15672/"

    def test_yaml_config_loading(self, tmp_path: Path) -> None:
        """测试从 YAML 文件解析多环境连接."""
        yaml_content = """
allow_write: true
default_connection: cluster_a
connections:
  cluster_a:
    amqp_url: amqp://user1:pwd1@host1:5672/v1
    management_url: http://user1:pwd1@host1:15672/
  cluster_b:
    amqp_url: amqp://user2:pwd2@host2:5672/v2
"""
        yaml_file = tmp_path / "connections.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_path=yaml_file)
        assert config.allow_write is True
        assert config.default_connection_name == "cluster_a"
        assert len(config.connections) == 2

        conn_a = config.get_connection("cluster_a")
        assert conn_a.masked_amqp_url == "amqp://user1:***@host1:5672/v1"
        assert conn_a.masked_management_url == "http://user1:***@host1:15672/"

        conn_b = config.get_connection("cluster_b")
        assert conn_b.masked_amqp_url == "amqp://user2:***@host2:5672/v2"
        assert conn_b.masked_management_url is None

        # 验证 default 别名自动回退到配置声明的 default_connection ("cluster_a")
        default_fallback = config.get_connection("default")
        assert default_fallback.name == "cluster_a"
        default_no_arg = config.get_connection()
        assert default_no_arg.name == "cluster_a"

    def test_list_connections(self) -> None:
        """测试 list_connections 脱敏返回."""
        cfg = RabbitMQServerConfig(
            connections={
                "c1": RabbitMQConnectionConfig(
                    name="c1",
                    amqp_url="amqp://u:p@host:5672/",
                    management_url="http://u:p@host:15672/",
                )
            }
        )
        items = cfg.list_connections()
        assert len(items) == 1
        assert items[0]["name"] == "c1"
        assert items[0]["amqp_url"] == "amqp://u:***@host:5672/"
        assert items[0]["management_url"] == "http://u:***@host:15672/"
        assert items[0]["has_management"] is True

    def test_global_config_lifecycle(self) -> None:
        """测试全局配置单例获取、设置与重置."""
        reset_global_config()
        initial = get_global_config()
        assert initial is not None

        custom = RabbitMQServerConfig(allow_write=True)
        set_global_config(custom)
        assert get_global_config().allow_write is True

        reset_global_config()
        assert get_global_config().allow_write is False
