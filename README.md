# atengk-mcp-server-rabbitmq

<p align="center">
  <strong>🐰 专为 LLM 与 AI Agent 打造的生产级 RabbitMQ Model Context Protocol (MCP) 服务端</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/atengk-mcp-server-rabbitmq/">
    <img src="https://img.shields.io/pypi/v/atengk-mcp-server-rabbitmq?style=flat-square&color=blue" alt="PyPI Version" />
  </a>
  <a href="https://pypi.org/project/atengk-mcp-server-rabbitmq/">
    <img src="https://img.shields.io/pypi/pyversions/atengk-mcp-server-rabbitmq?style=flat-square" alt="Python Versions" />
  </a>
  <a href="https://github.com/atengk/mcp-server-rabbitmq/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/atengk/mcp-server-rabbitmq/ci.yml?branch=main&label=CI&style=flat-square" alt="CI Status" />
  </a>
  <a href="https://github.com/atengk/mcp-server-rabbitmq/releases">
    <img src="https://img.shields.io/github/v/release/atengk/mcp-server-rabbitmq?style=flat-square" alt="GitHub Release" />
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square" alt="License" />
  </a>
  <a href="https://modelcontextprotocol.io/">
    <img src="https://img.shields.io/badge/MCP-2024--11--05-green.svg?style=flat-square" alt="MCP Protocol" />
  </a>
</p>

专为大语言模型（LLM）与各类 AI Agent 打造的高性能、安全可控的生产级 RabbitMQ 模型上下文协议（Model Context Protocol, MCP）服务端。已正式发布至 [PyPI](https://pypi.org/project/atengk-mcp-server-rabbitmq/)，支持开箱即用。

为智能体提供直观可靠的 AMQP 拓扑声明（Exchange / Queue / Binding）、消息可靠发布、零损采样 (Peek)、受控消费拉取、外部微服务 TCP 连接诊断、活跃信道未确认消息积压排查及集群大盘监控全套能力。

---

## ⚡ 快速开始 (Quick Start)

### 方式 1：使用 `uvx` 免安装直接运行（强烈推荐）

无需手动创建 Python 虚拟环境，借助现代包管理工具 `uv` 即可直接拉取并运行最新版：

```bash
# 只读探查模式（默认连接本地 RabbitMQ）
uvx atengk-mcp-server-rabbitmq --url "amqp://guest:guest@localhost:5672/"

# 启用 Management HTTP API 并开启写门禁（允许声明拓扑、清空队列及发送消息）
uvx atengk-mcp-server-rabbitmq \
  --url "amqp://guest:guest@localhost:5672/" \
  --management-url "http://guest:guest@localhost:15672" \
  --allow-write

# 启动常驻 HTTP SSE 服务（监听 0.0.0.0:8000）
uvx atengk-mcp-server-rabbitmq \
  --url "amqp://guest:guest@localhost:5672/" \
  --transport sse --host 0.0.0.0 --port 8000
```

### 方式 2：使用 `pip` 安装运行

```bash
pip install atengk-mcp-server-rabbitmq

# 启动服务
atengk-mcp-server-rabbitmq --url "amqp://guest:guest@localhost:5672/" --allow-write
```

### 方式 3：Docker 容器化运行

```bash
# 启动常驻 HTTP SSE 服务（默认暴露 8000 端口）
docker-compose up -d
```

---

## 🤖 通用 AI 客户端配置 (Generic MCP Client Configuration)

本服务端完全遵循开放的 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 规范，**通用兼容所有支持标准 MCP 协议的宿主环境与 AI Agent 客户端**（如 Claude Desktop、Cursor、Cline、Windsurf、Continue、Chatbox 等）。

你可以在任意 MCP 客户端的配置文件中，根据使用偏好选择 **命令行参数传参** 或 **环境变量传参**。

### 范式 A：通过命令行参数传参 (Arguments)

在客户端配置中直接通过 `args` 数组传入连接与安全选项：

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

> 💡 *若系统已通过 `pip install` 全局安装，可直接将 `"command": "uvx"` 及其下方的 `"atengk-mcp-server-rabbitmq"` 简写为 `"command": "atengk-mcp-server-rabbitmq"`。*

### 范式 B：通过环境变量传参 (Environment Variables)

若客户端推荐通过 `env` 注入敏感连接凭据或便于统一管理，可采用环境变量方式：

```json
{
  "mcpServers": {
    "rabbitmq": {
      "command": "uvx",
      "args": [
        "atengk-mcp-server-rabbitmq"
      ],
      "env": {
        "MCP_RABBITMQ_URL": "amqp://guest:guest@localhost:5672/",
        "MCP_RABBITMQ_MANAGEMENT_URL": "http://guest:guest@localhost:15672",
        "MCP_RABBITMQ_ALLOW_WRITE": "true"
      }
    }
  }
}
```

### 范式 C：连接远程常驻 HTTP SSE 服务端 (Remote SSE)

若 RabbitMQ MCP 服务端已在远程服务器或 Docker 容器中常驻启动（启用 SSE 传输模式）：

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

## ⚙️ 命令行参数与环境变量全景速查表

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

## 📁 多环境实例连接配置 (`connections.yaml`)

当需要同时连接多套 RabbitMQ 集群（如开发、测试、生产环境）时，可使用 YAML 配置文件：

1. 复制参考模板 [`connections.example.yaml`](./connections.example.yaml)：
   ```bash
   cp connections.example.yaml connections.yaml
   ```
2. 启动时通过 `-c` 参数指定配置文件：
   ```bash
   atengk-mcp-server-rabbitmq --config connections.yaml
   ```

---

## 🛡️ 生产级安全防护体系

- **强只读写保护门禁 (ADR-0002)**：未显式开启 `--allow-write` 时，任何破坏性变更（声明拓扑、清空队列、物理出队 ACK、发布消息）一律被即时阻断并返回结构化错误；
- **高危指令二次确认机制**：清空与删除操作要求必须传入 `confirm=True`，未传时仅返回受影响资源预估报告，绝不发生物理执行；
- **零损采样 (Zero-Loss Peek)**：队列采样读取后在退出阶段统一延迟批量 `reject(requeue=True)`，保证队列消息数量与顺序完全零破坏；
- **全域凭据脱敏算法**：任何连接串、字典属性或错误堆栈中的密码与认证 Token 统一替换为 `***`，彻底阻断大模型会话凭证泄露。

---

## 🤝 参与贡献

欢迎任何形式的贡献、Issue 反馈与功能提案！请在发起 PR 前阅读我们的 [贡献指南 (CONTRIBUTING.md)](./CONTRIBUTING.md)。

---

## 📄 开源许可证

本项目基于 [Apache License 2.0](./LICENSE) 协议开源。
