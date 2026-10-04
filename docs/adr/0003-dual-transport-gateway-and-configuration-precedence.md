# 采用 Stdio 管道与常驻 HTTP SSE 双模通信及参数分层覆盖架构

## 背景与问题陈述 (Context)

RabbitMQ MCP 服务端面临两类典型的下游使用场景：
1. **个人本地开发与桌面客户端交互**：如 Claude Desktop、Cursor 等，要求通过标准输入输出（Stdio）管道直接进程挂载，零端口占用，启动迅速且网络强隔离；
2. **企业级私有化平台与远程 Agent 调度**：需要作为容器化常驻微服务运行（如 Docker Compose 或 Kubernetes Pod），对外暴露统一 HTTP Server-Sent Events (SSE) 流式端点供远程多租户访问。

同时，运维人员在不同环境（本地快速测试、CI 管道、多环境配置）切换时，需要清晰确定的配置生效优先级，防止出现配置混淆。

## 架构决策 (Decision)

我们决定基于 FastMCP 装配双模传输网关，并制定强确定性的配置分层覆盖体系：

1. **双模通信网关 (Dual-Transport Gateway)**：
   - 默认采用 `stdio` 传输模式，服务日志强制重定向至 `sys.stderr`，保障 `sys.stdout` 作为 JSON-RPC 纯净通信管道；
   - 支持通过 `-t sse` 切换为常驻 HTTP SSE 网关模式，暴露 `/sse` 连接端点与 `/messages` 交互路由；
   - 生产级安全防护：启用内置 DNS 重绑定防护（DNS Rebinding Protection），校验合法主机头，防止恶意浏览器网页非法穿透本地私有网络。

2. **参数优先级三层覆盖准则 (Configuration Precedence)**：
   - **第一优先级（最高）**：CLI 显式命令行参数（如 `--url`, `--broker-host`, `--broker-port`, `-u`, `-P`, `--vhost`, `--ssl`, `--management-port`, `--allow-write`, `--transport`）；
   - **第二优先级（中等）**：系统环境变量（如 `MCP_RABBITMQ_HOST`, `MCP_RABBITMQ_PORT`, `MCP_RABBITMQ_USERNAME`, `MCP_RABBITMQ_PASSWORD`, `MCP_RABBITMQ_URL`）；
   - **第三优先级（基线）**：静态配置文件（`connections.yaml` 或 `-c/--config` 指定路径）。

3. **分立参数命名空间防冲突与深度融合机制 (Split Parameters & Deep Merging)**：
   - **命名空间隔离**：网关自身监听地址与端口严格限定为 `--host` 与 `-p, --port`；目标 RabbitMQ Broker 连接参数采用专用命名空间 `--broker-host`（别名 `--rmq-host`）、`--broker-port`（别名 `--rmq-port`）、`-u/--username`、`-P/--password`、`--vhost`、`--ssl`，绝不混淆；
   - **深度融合覆盖**：支持整体连接串与分立参数并存。当同时传入基础 URL 与分立参数（例如通过环境变量注入 `MCP_RABBITMQ_URL` 但在 CLI 传入 `-P custom_pwd`）时，服务端自动解析并以分立参数对 URL 内对应字段执行精确替换，保持其余拓扑信息不变。

## 方案权衡 (Considered Options)

- **方案 A: 仅支持 Stdio 模式**
  - *优点*：实现极简，无网络安全与端口冲突隐患；
  - *劣势*：无法支持 Docker 常驻部署、私有云多 Agent 平台共享与云端远程接入。
- **方案 B: 仅支持 HTTP SSE 模式**
  - *优点*：支持常驻与远程调用；
  - *劣势*：破坏本地桌面客户端开箱即用体验，本地多实例容易发生端口竞争冲突。
- **方案 C: Stdio / SSE 双模自适应网关（已采纳）**
  - *收益*：兼顾本地极客桌面直连与企业级云原生容器化常驻，通过标准 CLI 参数平滑无缝切换。
