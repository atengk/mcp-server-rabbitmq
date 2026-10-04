# 采用 AMQP 0-9-1 协议与 HTTP Management API 双核协作架构

在为大模型设计 RabbitMQ MCP 服务时，AMQP 0-9-1 协议专注于低延迟消息发布、通道复用与原生消费拉取，但该协议规范本身不具备全局拓扑检索指令（如列出所有交换机、队列和全局绑定）；而 RabbitMQ Management HTTP API 则提供了完备的集群指标、连接状态与拓扑大盘视图。我们决定采用 AMQP 与 HTTP API 双核协同架构：核心消息交互基于异步 `aio-pika`，拓扑清查与运维指标基于异步 `httpx`，并在未配置 HTTP API 时优雅降级为纯 AMQP 模式，以兼顾极致性能与全景运维视野。

## 方案权衡 (Considered Options)

- **纯 AMQP 模式**：放弃全局列表类工具，仅靠 Passive 声明探查队列，导致大模型无法探查已有资产拓扑；
- **纯 HTTP API 模式**：无法提供 AMQP 协议级通道能力、消息属性（Delivery Mode、Priority）与高性能连接池；
- **双核协作模式（已采纳）**：互补短板，形成完整的“探查-拓扑-收发-诊断”能力闭环。
