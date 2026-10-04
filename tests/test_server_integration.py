"""FastMCP 双模网关、CLI 命令行与端到端集成测试集.

@author Ateng
@since 2026-10-04
"""

import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mcp.types import CallToolResult, TextContent

from mcp_server_rabbitmq.cli import build_parser, main
from mcp_server_rabbitmq.core.config import get_global_config, reset_global_config
from mcp_server_rabbitmq.server import ALL_TOOLS, create_mcp_server


@pytest.fixture(autouse=True)
def clean_config_and_env() -> Iterator[None]:
    """每个测试前清理全局配置与测试环境变量."""
    reset_global_config()
    for key in (
        "MCP_RABBITMQ_URL",
        "MCP_RABBITMQ_MANAGEMENT_URL",
        "MCP_RABBITMQ_ALLOW_WRITE",
        "MCP_RABBITMQ_TRANSPORT",
        "MCP_RABBITMQ_SERVER_HOST",
        "MCP_RABBITMQ_SERVER_PORT",
    ):
        os.environ.pop(key, None)
    yield
    reset_global_config()


def test_create_mcp_server_registers_all_tools() -> None:
    """测试 FastMCP 服务实例初始化时成功注册全量 20 个 MCP 工具 (涵盖拓扑、消息、探活、诊断与别名)."""
    server = create_mcp_server()
    assert server is not None
    assert server.name == "atengk-mcp-server-rabbitmq"

    expected_tools = {
        "rabbitmq_list_connections",
        "rabbitmq_list_configured_brokers",
        "rabbitmq_ping",
        "rabbitmq_overview",
        "rabbitmq_list_exchanges",
        "rabbitmq_declare_exchange",
        "rabbitmq_delete_exchange",
        "rabbitmq_list_queues",
        "rabbitmq_get_queue",
        "rabbitmq_declare_queue",
        "rabbitmq_purge_queue",
        "rabbitmq_delete_queue",
        "rabbitmq_list_bindings",
        "rabbitmq_bind_queue",
        "rabbitmq_unbind_queue",
        "rabbitmq_publish_message",
        "rabbitmq_peek_messages",
        "rabbitmq_get_messages",
        "rabbitmq_list_client_connections",
        "rabbitmq_list_channels",
    }

    assert len(ALL_TOOLS) == 20
    tool_names = {getattr(fn, "__name__", str(fn)) for fn in ALL_TOOLS}
    assert tool_names == expected_tools


def test_cli_parser_defaults() -> None:
    """测试 CLI 命令行解析器默认参数."""
    parser = build_parser()
    args = parser.parse_args([])

    assert args.url is None
    assert args.management_url is None
    assert args.config is None
    assert args.allow_write is False
    assert args.transport == "stdio"
    assert args.host == "0.0.0.0"
    assert args.port == 8000
    assert args.verbose is False


def test_cli_parser_custom_args() -> None:
    """测试 CLI 显式参数解析."""
    parser = build_parser()
    args = parser.parse_args([
        "--url", "amqp://user:pass@127.0.0.1:5672/test",
        "--management-url", "http://user:pass@127.0.0.1:15672",
        "--allow-write",
        "--transport", "sse",
        "--host", "127.0.0.1",
        "--port", "9000",
        "--verbose",
    ])

    assert args.url == "amqp://user:pass@127.0.0.1:5672/test"
    assert args.management_url == "http://user:pass@127.0.0.1:15672"
    assert args.allow_write is True
    assert args.transport == "sse"
    assert args.host == "127.0.0.1"
    assert args.port == 9000
    assert args.verbose is True


def test_cli_args_override_env_priority() -> None:
    """测试命令行参数优先级高于环境变量 (CLI > ENV > Config)."""
    os.environ["MCP_RABBITMQ_URL"] = "amqp://env_user:env_pass@localhost:5672/"
    os.environ["MCP_RABBITMQ_ALLOW_WRITE"] = "false"
    os.environ["MCP_RABBITMQ_TRANSPORT"] = "stdio"

    mock_server = MagicMock()
    with patch("mcp_server_rabbitmq.cli.create_mcp_server", return_value=mock_server):
        main([
            "--url", "amqp://cli_user:cli_pass@localhost:5672/",
            "--allow-write",
            "--transport", "sse",
            "--port", "8888",
        ])

        config = get_global_config()
        assert config.allow_write is True
        default_conn = config.get_connection("default")
        assert "cli_user:cli_pass" in default_conn.amqp_url
        assert "env_user" not in default_conn.amqp_url

        mock_server.run.assert_called_once_with(
            transport="sse",
            host="0.0.0.0",
            port=8888,
        )


def test_cli_args_override_config_file_priority(tmp_path: Path) -> None:
    """测试命令行参数优先级高于 connections.yaml 配置文件 (CLI > Config)."""
    yaml_content = """
connections:
  default:
    name: default
    amqp_url: "amqp://yaml_user:yaml_pass@localhost:5672/"
    management_url: "http://yaml_user:yaml_pass@localhost:15672"
allow_write: false
"""
    cfg_file = tmp_path / "test_connections.yaml"
    cfg_file.write_text(yaml_content, encoding="utf-8")

    mock_server = MagicMock()
    with patch("mcp_server_rabbitmq.cli.create_mcp_server", return_value=mock_server):
        main([
            "--config", str(cfg_file),
            "--url", "amqp://cli_override:cli_override@localhost:5672/",
            "--allow-write",
        ])

        config = get_global_config()
        # 验证 CLI 成功覆盖了 YAML 配置文件的连接串和写门禁状态
        assert config.allow_write is True
        conn = config.get_connection("default")
        assert "cli_override:cli_override" in conn.amqp_url
        assert "yaml_user" not in conn.amqp_url
        # management_url 保留自 YAML
        assert conn.management_url == "http://yaml_user:yaml_pass@localhost:15672"


def test_cli_stdio_transport_run() -> None:
    """测试 Stdio 传输协议模式启动."""
    mock_server = MagicMock()
    with patch("mcp_server_rabbitmq.cli.create_mcp_server", return_value=mock_server):
        main(["--transport", "stdio"])
        mock_server.run.assert_called_once_with(transport="stdio")


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """测试 CLI 帮助文档输出友好说明与参数列表."""
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--url" in captured.out
    assert "--allow-write" in captured.out
    assert "--transport" in captured.out


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    """测试 CLI --version 准确输出版本号."""
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "1.0.4" in captured.out


@pytest.mark.asyncio
async def test_server_call_tool_roundtrip() -> None:
    """测试通过 FastMCP 实例直接分发调用 MCP 工具并获得符合契约的结构化结果."""
    server = create_mcp_server()
    res = await server.call_tool("rabbitmq_list_connections", {})
    assert isinstance(res, CallToolResult)
    assert res.is_error is False
    assert res.content is not None
    assert len(res.content) > 0
    first_item = res.content[0]
    assert isinstance(first_item, TextContent)
    assert "default" in first_item.text
    assert "***" in first_item.text


def test_sse_transport_app_routes() -> None:
    """测试 SSE 传输通道正确装配 /sse 与 /messages 路由端点 (AC #3)."""
    server = create_mcp_server()
    app = server.sse_app()
    assert app is not None

    route_paths = [getattr(r, "path", None) for r in app.routes]
    assert "/sse" in route_paths
    assert "/messages" in route_paths


def test_dockerfile_contract_and_security() -> None:
    """测试生产容器化 Dockerfile 满足多阶段构建与 appuser 非 root 运行安全契约 (AC #5)."""
    dockerfile_path = Path("Dockerfile")
    assert dockerfile_path.exists(), "根目录下必须包含 Dockerfile"
    content = dockerfile_path.read_text(encoding="utf-8")

    # 验证多阶段构建设计
    assert "FROM python:3.12-slim AS builder" in content
    assert "FROM python:3.12-slim AS runtime" in content

    # 验证安全最小权限账号 appuser (UID/GID 10001)
    assert "appuser" in content
    assert "10001" in content
    assert "USER appuser" in content

    # 验证端口暴露与启动入口
    assert "EXPOSE 8000" in content
    assert 'ENTRYPOINT ["atengk-mcp-server-rabbitmq"]' in content
    assert '"--transport", "sse"' in content


def test_cli_split_parameters_parsing() -> None:
    """测试 CLI 命令行解析器对分立连接参数的正确识别."""
    parser = build_parser()
    args = parser.parse_args([
        "--broker-host", "rmq.corp.internal",
        "--broker-port", "5672",
        "-u", "app_admin",
        "-P", "P@ss:w0rd#",
        "--vhost", "finance",
        "--ssl",
        "--management-port", "15672",
        "--management-ssl",
    ])
    assert args.broker_host == "rmq.corp.internal"
    assert args.broker_port == 5672
    assert args.username == "app_admin"
    assert args.password == "P@ss:w0rd#"
    assert args.vhost == "finance"
    assert args.ssl is True
    assert args.management_port == 15672
    assert args.management_ssl is True


def test_cli_split_parameters_execution_override() -> None:
    """测试通过 CLI 分立参数启动时自动融合组装合法连接配置."""
    mock_server = MagicMock()
    with patch("mcp_server_rabbitmq.cli.create_mcp_server", return_value=mock_server):
        main([
            "--broker-host", "10.0.1.20",
            "--broker-port", "5673",
            "-u", "custom_usr",
            "-P", "custom_pwd",
            "--vhost", "custom_vhost",
            "--management-port", "15673",
        ])

        config = get_global_config()
        conn = config.get_connection("default")
        assert conn.amqp_url == "amqp://custom_usr:custom_pwd@10.0.1.20:5673/custom_vhost"
        assert conn.masked_amqp_url == "amqp://custom_usr:***@10.0.1.20:5673/custom_vhost"
        assert conn.management_url == "http://custom_usr:custom_pwd@10.0.1.20:15673"
        assert conn.masked_management_url == "http://custom_usr:***@10.0.1.20:15673"


def test_cli_split_overrides_url_arg() -> None:
    """测试同时传入 --url 与分立参数时，分立参数深度覆盖对应字段."""
    mock_server = MagicMock()
    with patch("mcp_server_rabbitmq.cli.create_mcp_server", return_value=mock_server):
        main([
            "--url", "amqp://original_user:original_pass@cluster.internal:5672/v1",
            "-P", "cli_injected_password",
            "--broker-port", "5674",
        ])

        config = get_global_config()
        conn = config.get_connection("default")
        assert conn.amqp_url == "amqp://original_user:cli_injected_password@cluster.internal:5674/v1"

