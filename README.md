# mcp-server-rabbitmq

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

专为大语言模型（LLM）打造的高性能、安全可控的生产级 RabbitMQ 模型上下文协议（Model Context Protocol, MCP）服务，基于 Python 与 FastMCP 构建。

为大模型提供直观可靠的 AMQP 拓扑声明（Exchange / Queue / Binding）、消息发布与消费拉取、积压诊断、集群与连接状态监控及管理能力。

> 💡 **版本更新日志 (Changelog)**：
> 每一个正式版本的详细变动明细、关联 Issue 与贡献者致谢均由 `git-cliff` 自动维护，可直接前往 [GitHub Releases](https://github.com/atengk/mcp-server-rabbitmq/releases) 查看最新记录。

---

## ✨ 核心特性

- 🎯 **双核驱动支持**：
  - **AMQP 0-9-1 协议通道**：基于异步驱动高效处理消息生产、消息消费（单条拉取/批量采样）与拓扑管理；
  - **RabbitMQ Management HTTP API**：一站式检索集群节点、连接数、Channel 状态与队列堆积指标；
- 🛡️ **生产级安全守卫**：
  - **默认防护与危险操作二次确认**：对队列清空（Purge）、队列删除（Delete）、交换机解绑等高危动作实施显式确认机制；
  - **凭据脱敏保护**：对外连接与拓扑信息输出自动对敏感凭据实施掩码脱敏，杜绝安全泄露；
- 📦 **开箱即用与跨平台分发**：
  - 支持 `uvx` / `pipx` 零依赖瞬间拉起；
  - 提供预构建的生产级多架构 Docker 镜像（支持 AMD64 与 ARM64）；
  - 支持 Stdio 标准管道交互与常驻 HTTP SSE 双模通信。

---

## 📦 安装与快速运行

### 方式 1：使用 `uvx` 免安装直接运行（强烈推荐）

无需手动配置虚拟环境，借助现代 Python 包管理工具 `uv` 即可直接拉取并启动：

```bash
# 启动 Stdio 模式（连接本地 RabbitMQ 默认实例）
uvx atengk-mcp-server-rabbitmq --url "amqp://guest:guest@localhost:5672/"

# 配合 Management HTTP API 启用完整运维监控能力
uvx atengk-mcp-server-rabbitmq \
  --url "amqp://guest:guest@localhost:5672/" \
  --management-url "http://guest:guest@localhost:15672"
```

### 方式 2：使用 `pip` 安装运行

```bash
pip install atengk-mcp-server-rabbitmq

# 启动服务
atengk-mcp-server-rabbitmq --url "amqp://guest:guest@localhost:5672/"
```

### 方式 3：源码本地克隆与开发运行

```bash
git clone https://github.com/atengk/mcp-server-rabbitmq.git
cd mcp-server-rabbitmq

# 使用 uv 同步依赖与构建虚拟环境
uv sync

# 本地执行测试与运行
uv run pytest
uv run atengk-mcp-server-rabbitmq --url "amqp://guest:guest@localhost:5672/"
```

### 方式 4：使用 Docker 容器化运行

```bash
# 瞬态交互运行（stdio 管道）
docker run -i --rm \
  -e MCP_RABBITMQ_URL="amqp://guest:guest@host.docker.internal:5672/" \
  ghcr.io/atengk/mcp-server-rabbitmq:latest --transport stdio

# 常驻后台 HTTP SSE 服务端（暴露 8000 端口）
docker-compose up -d
```

---

## 🤝 参与贡献

欢迎任何形式的贡献、Issue 反馈与功能提案！请在发起 PR 前仔细阅读我们的 [贡献指南 (CONTRIBUTING.md)](./CONTRIBUTING.md)。

---

## 📄 开源许可证

本项目基于 [Apache License 2.0](./LICENSE) 协议开源。
