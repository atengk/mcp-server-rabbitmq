# 采用 AMQP 0-9-1 协议与 HTTP Management API 双核协作架构

## 背景与问题陈述 (Context)

在为大模型 (LLM) 与 AI Agent 设计生产级 RabbitMQ MCP 服务端时，面临协议能力与运维场景的本质冲突：
1. **AMQP 0-9-1 的协议局限**：AMQP 专注于低延迟消息发布、通道多路复用与原生消费拉取。然而作为数据流协议，其规范本身**未定义全局资产检索指令**（无法直接查询集群中已存在的所有交换机、所有队列及其全局绑定规则，也无法获知当前连入集群的外部微服务 TCP 连接与信道积压情况）；
2. **Management HTTP API 的优劣**：由 RabbitMQ Management 插件暴露的 HTTP RESTful 接口具备全景指标大盘、资源水位与连接监控，但通过 HTTP 轮询收发消息性能低下，且无法提供原生 AMQP 通道管理、确认机制与精细化消息头。

## 架构决策 (Decision)

我们决定采用 **AMQP 0-9-1 二进制协议（数据平面）与 HTTP Management API（管控平面）双核协作架构**：

1. **职责分离与客户端分工**：
   - **数据平面 (Data Plane)**：核心消息收发、零损采样 (Peek)、拓扑声明与绑定由基于异步事件循环的 `aio-pika` 驱动承担，直连 AMQP `5672`（或 SSL `5671`）端口；
   - **管控平面 (Control Plane)**：集群概览大盘、微服务物理 TCP 连接监控与活跃信道排障由基于异步连接池的 `httpx` 驱动承担，连接 Management HTTP `15672` 端口。
2. **非强制性与优雅降级机制 (Graceful Degradation)**：
   - Management API 设为可选扩展能力，绝不作为服务启动的前置硬性依赖；
   - 当用户仅配置 Broker 连接（未配置 Management API）时，全套 AMQP 消息与拓扑声明工具正常运作；
   - 当调用 `rabbitmq_overview` 或连接/信道排障工具时，系统返回清晰的结构化降级说明，说明 Management API 未启用，绝不抛出未捕获异常或阻断服务运行。
3. **认证信息智能继承**：
   - 分立参数与环境变量支持主机与凭据继承。指定 `--management-port 15672` 时，主机名与账号密码自动继承 Broker 配置，无需繁琐重复声明。

## 方案权衡 (Considered Options)

- **方案 A: 纯 AMQP 协议模式**
  - *优点*：依赖最少，仅需暴露单一 5672 端口；
  - *劣势*：无法向大模型提供全局资产大盘与外部微服务连接排障能力，丧失了运维诊断核心价值。
- **方案 B: 纯 HTTP Management API 模式**
  - *优点*：统一为单一 HTTP 客户端；
  - *劣势*：消息收发性能与延迟远落后于二进制协议，无法利用 AMQP 原生通道流控，且部分最小化 RabbitMQ 生产镜像默认未启用 Management 插件导致服务瘫痪。
- **方案 C: AMQP + HTTP 双核协作与优雅降级（已采纳）**
  - *收益*：兼顾原生二进制通信的高性能与 HTTP 管理接口的宏观全景视野，支持无 Management 插件时的平滑降级。

