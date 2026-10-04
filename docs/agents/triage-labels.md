# 分诊标签体系 (Triage Labels)

各项技能基于五个标准分诊角色进行协同。下表记录了本仓库 Issue 跟踪系统中的实际标签映射关系：

| mattpocock/skills 标准角色 | 本仓库实际标签 | 业务含义说明 |
| :------------------------- | :------------- | :----------- |
| `needs-triage`             | `needs-triage` | 待维护者评估与分诊 |
| `needs-info`               | `needs-info`   | 等待提报者补充更多上下文或复现信息 |
| `ready-for-agent`          | `ready-for-agent` | 需求规格明确，可交由离线 AI Agent 执行 |
| `ready-for-human`          | `ready-for-human` | 需要人工介入或人类工程师实操实现 |
| `wontfix`                  | `wontfix`      | 经评估不予处理或关闭 |

当技能要求执行角色操作时（例如“应用就绪离线 Agent 标签”），直接使用上表中对应的实际标签字符串。
