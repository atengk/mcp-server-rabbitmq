# atengk-mcp-server-rabbitmq

<p align="center">
  <strong>🐰 专为 LLM 打造的生产级 RabbitMQ Model Context Protocol (MCP) 服务端</strong>
</p>

<p align="center">
  <a href="https://github.com/atengk/mcp-server-rabbitmq/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/atengk/mcp-server-rabbitmq/ci.yml?branch=main&label=CI&style=flat-square" alt="CI Status" />
  </a>
  <a href="https://github.com/atengk/mcp-server-rabbitmq/releases">
    <img src="https://img.shields.io/github/v/release/atengk/mcp-server-rabbitmq?style=flat-square" alt="GitHub Release" />
  </a>
  <a href="https://pypi.org/project/atengk-mcp-server-rabbitmq/">
    <img src="https://img.shields.io/pypi/v/atengk-mcp-server-rabbitmq?style=flat-square" alt="PyPI Version" />
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square" alt="License" />
  </a>
  <a href="./CONTRIBUTING.md">
    <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square" alt="PRs Welcome" />
  </a>
  <a href="https://modelcontextprotocol.io/">
    <img src="https://img.shields.io/badge/MCP-2024--11--05-green.svg?style=flat-square" alt="MCP Protocol" />
  </a>
</p>

专为大语言模型（LLM）打造的高性能、安全可控的生产级 RabbitMQ 模型上下文协议（Model Context Protocol, MCP）服务端，基于 Python 与 FastMCP 构建。

为大模型提供直观可靠的 AMQP 拓扑声明（Exchange / Queue / Binding）、消息可靠发布、零损采样 (Peek)、受控消费拉取、外部微服务 TCP 连接诊断、活跃信道排障及集群大盘监控全套能力。

---

## ✨ 核心特性

- 🎯 **双核驱动支持 (ADR-0001)**：
  - **AMQP 0-9-1 协议通道**：基于异步 `aio-pika` 高性能处理消息发布、无损采样、受控拉取消费与核心拓扑受控声明；
  - **RabbitMQ Management HTTP API**：一站式检索集群节点、连接数、Channel 状态与队列堆积指标；未配置时支持优雅降级；
- 🛡️ **生产级三层安全守卫 (ADR-0002)**：
  - **默认强只读写保护门禁 (`--allow-write`)**：未开启写门禁时，严禁任何破坏性操作与消息写入；
  - **高危操作二次确认守卫 (`confirm=True`)**：清空队列（Purge）、删除队列（Delete）、删除交换机等高危指令强制要求二次确认，未确认时仅返回受影响预估报告；
  - **零损消息采样 (Peek)**：读取队列消息后自动在退出前统一延迟批量 `reject(requeue=True)`，保证队列消息数量与顺序完全零破坏，彻底防范重复迭代消费；
  - **全域凭据自动脱敏**：对外连接串、日志堆栈与客户端元数据自动对 `password`、`secret`、`token` 实施掩码脱敏，杜绝大模型回显凭证泄漏；
- 🌐 **双模通信网关与生产容器化 (ADR-0003)**：
  - 支持本地 Stdio 标准管道交互与企业级常驻 HTTP SSE 双模协议无缝切换；
  - 严格保障参数优先级：**CLI 命令行参数 > 系统环境变量 > `connections.yaml` 配置文件**；
  - 提供多架构（AMD64 / ARM64）非 root 用户容器镜像。

---

## 🛠️ 全量 MCP 工具矩阵 (20 Tools)

服务端完整装配并挂载以下 20 个 MCP 工具，模型可根据需要自主调用：

### 1. Broker 基础探活与配置管理 (4)

| 工具名称 | 功能描述 | 门禁约束 |
| :--- | :--- | :--- |
| `rabbitmq_list_connections` | 列出当前服务配置的所有 RabbitMQ 实例连接清单与脱敏地址 | 只读 |
| `rabbitmq_list_configured_brokers` | `rabbitmq_list_connections` 的语义强化别名，用于清晰区分配置实例与客户端物理链路 | 只读 |
| `rabbitmq_ping` | 测量与 RabbitMQ Broker 的 AMQP 链路往返延迟（ms） | 只读 |
| `rabbitmq_overview` | 获取集群节点状态、队列统计与全局消息吞吐大盘（无 HTTP API 时优雅降级） | 只读 |

### 2. 交换机、队列与绑定拓扑管理 (11)

| 工具名称 | 功能描述 | 门禁约束 |
| :--- | :--- | :--- |
| `rabbitmq_list_exchanges` | 查询交换机列表、类型及持久化配置属性 | 只读 |
| `rabbitmq_declare_exchange` | 受控声明新的交换机，支持 direct / fanout / topic / headers 类型 | 需 `--allow-write` |
| `rabbitmq_delete_exchange` | 删除指定交换机 | 需 `--allow-write` 且 `confirm=True` |
| `rabbitmq_list_queues` | 查询各队列就绪数、未确认数与消费者数 | 只读 |
| `rabbitmq_get_queue` | 获取单个队列深度指标（死信交换机、TTL、最大积压限制等） | 只读 |
| `rabbitmq_declare_queue` | 声明队列，支持死信路由 (`dlx`) 与最大积压策略 (`x-max-length`) | 需 `--allow-write` |
| `rabbitmq_purge_queue` | 清空指定队列中积压的消息 | 需 `--allow-write` 且 `confirm=True` |
| `rabbitmq_delete_queue` | 删除指定队列 | 需 `--allow-write` 且 `confirm=True` |
| `rabbitmq_list_bindings` | 查询交换机与队列之间的 Routing Key 绑定关系规则 | 只读 |
| `rabbitmq_bind_queue` | 将队列绑定到目标交换机 | 需 `--allow-write` |
| `rabbitmq_unbind_queue` | 解除队列与交换机之间的绑定关系 | 需 `--allow-write` |

### 3. 消息发布、零损采样与受控拉取 (3)

| 工具名称 | 功能描述 | 门禁约束 |
| :--- | :--- | :--- |
| `rabbitmq_publish_message` | 向指定 Exchange/Routing Key 发布消息，支持字典自动序列化与自定义属性 | 需 `--allow-write` |
| `rabbitmq_peek_messages` | 对队列头部实施无损诊断采样，自动批量 Requeue 归还队首，消息零丢失不出队 | 只读 |
| `rabbitmq_get_messages` | 受控拉取消费消息，默认 `ack=False` 仅拉取，传 `ack=True` 物理确认出队 | `ack=True` 需 `--allow-write` |

### 4. 客户端连接与活跃信道排障诊断 (2)

| 工具名称 | 功能描述 | 门禁约束 |
| :--- | :--- | :--- |
| `rabbitmq_list_client_connections` | 排查外部微服务客户端连入 RabbitMQ 的物理 TCP 链路、信道数与收发吞吐速率 | 只读 |
| `rabbitmq_list_channels` | 诊断活跃信道未确认消息积压 (`unack`)、QoS Prefetch 限额与消费速率 | 只读 |

---

## 💻 Claude Desktop 客户端配置指南

编辑本地 Claude Desktop 配置文件 `claude_desktop_config.json`：
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### 方式 A：Stdio 管道模式（推荐，借助 uvx 零依赖直启）

```json
{
  "mcpServers": {
    "rabbitmq": {
      "command": "uvx",
      "args": [
        "atengk-mcp-server-rabbitmq",
        "--url",
        "amqp://guest:guest@localhost:5672/",
        "--management-url",
        "http://guest:guest@localhost:15672",
        "--allow-write"
      ]
    }
  }
}
```

### 方式 B：连接常驻 HTTP SSE 服务端

若已通过 Docker 或后台拉起 SSE 模式：

```json
{
  "mcpServers": {
    "rabbitmq": {
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

---

## 📦 安装与快速运行

### 1. 使用 `uvx` 免安装直接运行（强烈推荐）

```bash
# 启动 Stdio 模式（只读探查模式）
uvx atengk-mcp-server-rabbitmq --url "amqp://guest:guest@localhost:5672/"

# 开启写权限并配合 Management HTTP API 启用完整运维监控能力
uvx atengk-mcp-server-rabbitmq \
  --url "amqp://guest:guest@localhost:5672/" \
  --management-url "http://guest:guest@localhost:15672" \
  --allow-write

# 启动常驻 HTTP SSE 服务（监听 0.0.0.0:8000）
uvx atengk-mcp-server-rabbitmq \
  --url "amqp://guest:guest@localhost:5672/" \
  --transport sse --host 0.0.0.0 --port 8000
```

### 2. 多环境配置文件运行 (`connections.yaml`)

参考 [`connections.example.yaml`](./connections.example.yaml) 配置多套环境实例：

```bash
cp connections.example.yaml connections.yaml
# 使用配置文件启动
atengk-mcp-server-rabbitmq --config connections.yaml
```

### 3. Docker Compose 容器化部署

```bash
# 启动常驻 HTTP SSE 服务（默认暴露 8000 端口）
docker-compose up -d
```

---

## ⚙️ 命令行参数与环境变量速查表

| CLI 参数 | 对应环境变量 | 默认值 | 参数说明 |
| :--- | :--- | :--- | :--- |
| `--url` | `MCP_RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/` | RabbitMQ AMQP 0-9-1 连接协议串 |
| `--management-url` | `MCP_RABBITMQ_MANAGEMENT_URL` | `None` | RabbitMQ Management HTTP API 访问地址 |
| `-c, --config` | `MCP_RABBITMQ_CONFIG` | `None` | 多环境连接配置文件路径（`connections.yaml`） |
| `--allow-write` | `MCP_RABBITMQ_ALLOW_WRITE` | `False` | 开启写保护门禁放行标志（允许声明、清空、发布消息） |
| `-t, --transport` | `MCP_RABBITMQ_TRANSPORT` | `stdio` | MCP 传输层协议：`stdio` 或 `sse` |
| `--host` | `MCP_RABBITMQ_SERVER_HOST` | `0.0.0.0` | 常驻 HTTP SSE 网关监听网络地址 |
| `-p, --port` | `MCP_RABBITMQ_SERVER_PORT` | `8000` | 常驻 HTTP SSE 网关监听端口 |
| `-v, --verbose` | `MCP_RABBITMQ_LOG_LEVEL` | `False` (INFO) | 启用详细 DEBUG 日志输出 |
| `--version` | - | - | 显示当前服务版本号并退出 |
| `-h, --help` | - | - | 显示帮助信息与参数用法 |

> 📌 **参数生效优先级**：**CLI 显式参数 > 系统环境变量 > `connections.yaml` 配置文件**。

---

## 🤝 参与贡献

欢迎任何形式的贡献、Issue 反馈与功能提案！请在发起 PR 前仔细阅读我们的 [贡献指南 (CONTRIBUTING.md)](./CONTRIBUTING.md)。

---

## 📄 开源许可证

本项目基于 [Apache License 2.0](./LICENSE) 协议开源。
