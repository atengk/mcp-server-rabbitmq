# 领域文档规范 (Domain Docs)

定义工程技能在探索与理解代码库时，如何阅读与消费本项目的业务领域文档。

## 探索代码库前应预先阅读的文件

- 仓库根目录下的 **`CONTEXT.md`**，或者
- 根目录下的 **`CONTEXT-MAP.md`**（若存在则指向各子上下文专属的 `CONTEXT.md`，按需调阅对应模块的文档）；
- **`docs/adr/`**：阅读与当前即将修改的业务范围相关的架构决策记录（ADR）。在多上下文仓库中，同步检查 `src/<context>/docs/adr/`。

若上述文件尚不存在，**静默继续执行**，无需报错，也无需主动要求预先创建。`/domain-modeling` 技能（通过 `/grill-with-docs` 或 `/improve-codebase-architecture` 触发）会在实际确立领域术语或架构决策时按需懒加载创建它们。

## 目录拓扑结构

单上下文仓库（绝大多数项目与当前项目结构）：

```text
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-amqp-topology-model.md
│   └── 0002-async-pika-driver.md
└── src/
```

多上下文仓库（仅当根目录存在 `CONTEXT-MAP.md` 时）：

```text
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← 全局跨模块架构决策
└── src/
    ├── amqp/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← 模块特异性决策
    └── management/
        ├── CONTEXT.md
        └── docs/adr/
```

## 统一采用词汇表术语 (Glossary)

当输出涉及业务领域概念时（包括 Issue 标题、重构方案、方案假设、测试用例名称等），必须严格使用 `CONTEXT.md` 中定义的标准术语，杜绝自行创造词汇表中明确规避的近义词或机翻别名。

若所需概念尚未收录于词汇表中，这是一个明确信号——要么你在使用本项目未认可的非标术语（需要反思修正），要么存在真实的领域术语缺口（应记录并交由 `/domain-modeling` 补充完善）。

## 显式标注 ADR 决策冲突

如果你的设计或改动提议与既有的 ADR 产生分歧，必须在方案中显式暴露冲突背景并阐明重审理由，严禁静默覆盖已有决策：

> ⚠️ *与已有决策 ADR-0002 (选用 aio-pika 作为底层驱动) 存在冲突——但提议重新审视该决策，因为……*
