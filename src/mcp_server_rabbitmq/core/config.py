"""RabbitMQ 服务端配置中心与凭据脱敏实现.

@author Ateng
@since 2026-10-04
"""

import os
import re
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yaml
from pydantic import BaseModel, Field

_PASSWORD_PATTERN = re.compile(r"([a-zA-Z0-9+.-]+://[^:/@\s]+:)([^@\s]+)(@)")


def mask_url(url: str | None) -> str | None:
    """对连接 URL 或包含连接 URL 的错误文本中的密码进行脱敏，替换为掩码 '***'.

    支持单独 URL（包括密码含 '@'）与长文本错误堆栈中嵌入的 URL 凭据脱敏。

    @param url 原始连接 URL 或包含 URL 的文本字符串，支持 None 或空串
    @return 脱敏后的字符串
    """
    if not url:
        return url

    # 1. 若为标准独立 URL 且包含凭据，优先通过 urlsplit 精准脱敏（支持密码内含 '@' 等特殊符号）
    try:
        parts = urlsplit(url)
        if parts.scheme and parts.netloc and "@" in parts.netloc:
            user_info, _, host_info = parts.netloc.rpartition("@")
            if ":" in user_info:
                user, _, _ = user_info.partition(":")
                masked_netloc = f"{user}:***@{host_info}"
                return urlunsplit((parts.scheme, masked_netloc, parts.path, parts.query, parts.fragment))
    except (ValueError, AttributeError):
        pass

    # 2. 复合错误堆栈/长文本正则脱敏替换
    return _PASSWORD_PATTERN.sub(r"\g<1>***\g<3>", url)


class RabbitMQConnectionConfig(BaseModel):
    """RabbitMQ 单个实例连接元数据配置."""

    name: str = Field(default="default", description="连接标识别名")
    amqp_url: str = Field(..., description="AMQP 0-9-1 连接协议串")
    management_url: str | None = Field(default=None, description="HTTP Management API 访问基地址")

    @property
    def masked_amqp_url(self) -> str:
        """获取脱敏后的 AMQP 连接串."""
        masked = mask_url(self.amqp_url)
        return masked if masked is not None else ""

    @property
    def masked_management_url(self) -> str | None:
        """获取脱敏后的 Management API 地址."""
        return mask_url(self.management_url)

    def to_summary_dict(self) -> dict[str, Any]:
        """生成脱敏后的连接元数据概要字典.

        @return 脱敏连接概要信息字典
        """
        return {
            "name": self.name,
            "amqp_url": self.masked_amqp_url,
            "management_url": self.masked_management_url,
            "has_management": self.management_url is not None,
        }


class RabbitMQServerConfig(BaseModel):
    """RabbitMQ MCP 服务端运行时全局拓扑与安全配置."""

    connections: dict[str, RabbitMQConnectionConfig] = Field(
        default_factory=dict, description="已配置的所有实例连接字典"
    )
    allow_write: bool = Field(default=False, description="是否允许写入与破坏性操作门禁开关")
    default_connection_name: str = Field(default="default", description="默认连接别名")

    def get_connection(self, name: str = "default") -> RabbitMQConnectionConfig:
        """根据连接名称检索配置对象.

        若请求 'default' 且未显式定义名为 'default' 的连接，则自动回退到配置指定的 default_connection_name。

        @param name 连接别名，默认为 'default'
        @return 对应的连接配置对象
        @throws KeyError 当指定的连接别名不存在时抛出
        """
        target_name = name or self.default_connection_name
        if target_name == "default" and target_name not in self.connections:
            target_name = self.default_connection_name

        if target_name not in self.connections:
            available = list(self.connections.keys())
            raise KeyError(f"未找到指定的 RabbitMQ 连接配置: '{name}'，当前可用连接列表: {available}")
        return self.connections[target_name]

    def list_connections(self) -> list[dict[str, Any]]:
        """获取脱敏后的所有可用连接列表.

        @return 连接概要字典列表，空时返回空列表
        """
        return [conn.to_summary_dict() for conn in self.connections.values()]


def _parse_bool(value: str | None, default: bool = False) -> bool:
    """解析布尔字符串环境变量."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(
    config_path: Path | str | None = None,
    allow_write: bool | None = None,
) -> RabbitMQServerConfig:
    """加载并解析 RabbitMQ MCP 服务端配置.

    加载优先级：显式入参 > 环境变量指定文件 > 默认 connections.yaml > 环境变量 URL 兜底。

    @param config_path 配置文件路径
    @param allow_write 显式指定的写保护门禁开关
    @return 组装完成的 RabbitMQServerConfig 对象
    """
    resolved_path: Path | None = None
    if config_path:
        resolved_path = Path(config_path)
    elif env_path := os.getenv("MCP_RABBITMQ_CONFIG_PATH"):
        resolved_path = Path(env_path)
    elif Path("connections.yaml").is_file():
        resolved_path = Path("connections.yaml")

    connections_map: dict[str, RabbitMQConnectionConfig] = {}
    cfg_allow_write = False
    default_conn_name = "default"

    # 1. 尝试从 YAML 配置文件解析
    if resolved_path and resolved_path.is_file():
        with resolved_path.open("r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}

        cfg_allow_write = bool(raw_data.get("allow_write", False))
        default_conn_name = str(raw_data.get("default_connection", "default"))

        raw_conns = raw_data.get("connections", {})
        if isinstance(raw_conns, dict):
            for name, conn_info in raw_conns.items():
                if isinstance(conn_info, dict):
                    connections_map[name] = RabbitMQConnectionConfig(
                        name=name,
                        amqp_url=str(conn_info.get("amqp_url", "")),
                        management_url=conn_info.get("management_url"),
                    )

    # 2. 环境变量补充与覆盖
    env_amqp = os.getenv("MCP_RABBITMQ_URL")
    env_mgmt = os.getenv("MCP_RABBITMQ_MANAGEMENT_URL")
    if env_amqp or not connections_map:
        base_amqp = env_amqp or "amqp://guest:guest@localhost:5672/"
        connections_map["default"] = RabbitMQConnectionConfig(
            name="default",
            amqp_url=base_amqp,
            management_url=env_mgmt,
        )

    # 3. 计算最终门禁状态
    env_allow_write = _parse_bool(os.getenv("MCP_RABBITMQ_ALLOW_WRITE"), default=cfg_allow_write)
    final_allow_write = allow_write if allow_write is not None else env_allow_write

    return RabbitMQServerConfig(
        connections=connections_map,
        allow_write=final_allow_write,
        default_connection_name=default_conn_name,
    )


_GLOBAL_CONFIG: RabbitMQServerConfig | None = None
_CONFIG_LOCK = threading.Lock()


def get_global_config() -> RabbitMQServerConfig:
    """获取当前进程全局配置实例，未初始化时自动加载并加锁保护."""
    global _GLOBAL_CONFIG
    if _GLOBAL_CONFIG is None:
        with _CONFIG_LOCK:
            if _GLOBAL_CONFIG is None:
                _GLOBAL_CONFIG = load_config()
    return _GLOBAL_CONFIG


def set_global_config(config: RabbitMQServerConfig) -> None:
    """线程安全设置全局配置实例."""
    global _GLOBAL_CONFIG
    with _CONFIG_LOCK:
        _GLOBAL_CONFIG = config


def reset_global_config() -> None:
    """线程安全重置全局配置实例为初始状态."""
    global _GLOBAL_CONFIG
    with _CONFIG_LOCK:
        _GLOBAL_CONFIG = None
