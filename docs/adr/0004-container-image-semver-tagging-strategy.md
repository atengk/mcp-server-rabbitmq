# 容器镜像多层级语义化标签与自动化发布策略

## 背景与问题陈述 (Context)

在构建生产级 RabbitMQ MCP 服务端容器镜像分发流水线时，面临多平台兼容性与版本标签体系的以下挑战：
1. **容器标签缺失与解析异常**：由于 CI 检出步骤默认采用浅克隆（`fetch-depth: 1`），缺少完整的 Git 历史与 Tag 元数据，导致 `docker/metadata-action` 无法精确比对历史版本，进而在特定场景下遗漏 `:latest` 镜像标签；
2. **多架构 Attestation 幽灵层**：Docker Buildx 默认启用的 SLSA Provenance 与 SBOM 证明文件会在多架构（linux/amd64 与 linux/arm64）镜像清单中注入带有 `unknown/unknown` 平台的 Attestation Manifest 层，导致很多旧版 Docker Daemon、Kubernetes 集群与私有 Registry 在拉取时报错；
3. **标签层级颗粒度不统一**：工业级容器镜像需要为不同稳定性诉求的用户提供多颗粒度更新策略（如只跟踪主版本的大版本升级、跟踪次版本的小版本更新、锁定 Patch 的精确版本以及默认最新稳定版）。

## 架构决策 (Decision)

我们决定对标 [`atengk/oss-template`](https://github.com/atengk/oss-template) 规范，在 GitHub Actions 中建立**全量历史比对、四级 SemVer 标签体系与纯净镜像发布策略**：

1. **全量检出保障版本比对精度**：
   - 容器镜像构建任务中的 `actions/checkout@v4` 显式配置 `fetch-depth: 0`，确保拉取完整历史与所有 Tag，为语义化版本推导提供准确基准。
2. **四级语义化标签体系 (SemVer Hierarchy)**：
   - `:latest`：显式声明 `flavor: latest=true`，确保每一次正式语义化发布均必定推送最新的稳定版指针；
   - `:{{version}}`（例如 `1.0.4`）：精确锁定 Patch 级别的不可变发版标签；
   - `:{{major}}.{{minor}}`（例如 `1.0`）：自动滚动更新当前小版本的最新安全补丁；
   - `:{{major}}`（例如 `1`）：自动滚动更新当前大版本的最新特性与补丁。
3. **彻底抑制 Attestation 幽灵 Manifest**：
   - 在 `docker/build-push-action@v5` 中强制配置 `provenance: false` 与 `sbom: false`，彻底消除 `unknown/unknown` 平台架构层，仅推送标准的 Multi-arch OCI 镜像 Manifest List。

## 方案权衡 (Considered Options)

- **方案 A: 仅保留单一 `:latest` 或单一版本号标签**
  - *缺点*：缺乏灰度与渐进式更新能力，用户无法在锁定版本与自动补丁之间灵活选择。
- **方案 B: 仅依赖 `latest=auto` 自动判定**
  - *缺点*：在历史分支检出不完全或非主干 Tag 触发时容易产生静默漏打 `latest` 标签的问题。
- **方案 C: 全量 Git 检出 + 3 级 SemVer 模板 + 显式 `latest=true` 兜底（已采纳）**
  - *收益*：兼具工业级语义化版本梯队与 100% 确定性，全平台兼容且消除幽灵 Attestation 层。
