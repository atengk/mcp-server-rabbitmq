"""RabbitMQ HTTP Management API 异步客户端与拓扑指标采集.

@author Ateng
@since 2026-10-04
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class ManagementClient:
    """RabbitMQ Management HTTP 接口异步客户端封装."""

    def __init__(self, base_url: str | None, timeout: float = 10.0) -> None:
        """初始化 ManagementClient.

        @param base_url HTTP Management API 根地址，允许为 None
        @param timeout HTTP 请求超时时间（秒）
        """
        self.raw_base_url = base_url
        self.timeout = timeout
        self.base_url: str | None
        if base_url:
            cleaned = base_url.rstrip("/")
            self.base_url = cleaned if cleaned.endswith("/api") else f"{cleaned}/api"
        else:
            self.base_url = None

    @property
    def is_available(self) -> bool:
        """检查当前客户端是否已配置 Management API 地址."""
        return self.base_url is not None

    def _get_url(self, path: str) -> str:
        """拼装目标 API 完整路径."""
        if not self.base_url:
            raise ValueError("未配置 RabbitMQ Management API 访问地址")
        clean_path = path.lstrip("/")
        return f"{self.base_url}/{clean_path}"

    async def get_overview(self) -> dict[str, Any]:
        """获取集群概览指标."""
        url = self._get_url("overview")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data

    async def list_exchanges(self, vhost: str | None = None) -> list[dict[str, Any]]:
        """查询交换机列表，支持指定 vhost 过滤."""
        path = f"exchanges/{quote(vhost, safe='')}" if vhost else "exchanges"
        url = self._get_url(path)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            items: list[dict[str, Any]] = resp.json()
            return items

    async def list_queues(self, vhost: str | None = None) -> list[dict[str, Any]]:
        """查询队列列表及核心指标，支持指定 vhost 过滤."""
        path = f"queues/{quote(vhost, safe='')}" if vhost else "queues"
        url = self._get_url(path)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            items: list[dict[str, Any]] = resp.json()
            return items

    async def get_queue(self, queue: str, vhost: str = "/") -> dict[str, Any]:
        """获取指定队列的深度元数据."""
        encoded_vhost = quote(vhost, safe="")
        encoded_queue = quote(queue, safe="")
        url = self._get_url(f"queues/{encoded_vhost}/{encoded_queue}")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data

    async def list_bindings(
        self,
        vhost: str | None = None,
        queue: str | None = None,
        exchange: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询路由绑定关系，支持按 vhost、queue 或 exchange 过滤."""
        if vhost and queue:
            path = f"queues/{quote(vhost, safe='')}/{quote(queue, safe='')}/bindings"
        elif vhost and exchange:
            path = f"exchanges/{quote(vhost, safe='')}/{quote(exchange, safe='')}/bindings/source"
        elif vhost:
            path = f"bindings/{quote(vhost, safe='')}"
        else:
            path = "bindings"

        url = self._get_url(path)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            items: list[dict[str, Any]] = resp.json()
            return items
