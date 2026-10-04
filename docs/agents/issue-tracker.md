# 任务跟踪系统 (Issue Tracker): GitHub

本项目的任务、需求规格 (Spec) 与缺陷统一作为 GitHub Issues 进行维护。所有自动化与命令行操作统一使用 `gh` CLI。

## 操作规范

- **创建 Issue**：`gh issue create --title "..." --body "..."`。多行正文建议使用 Here-Doc 语法。
- **查看 Issue**：`gh issue view <number> --comments`，可通过 `jq` 过滤评论并获取标签。
- **列出 Issues**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，按需配合 `--label` 与 `--state` 过滤。
- **发表评论**：`gh issue comment <number> --body "..."`
- **添加 / 移除标签**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **关闭 Issue**：`gh issue close <number> --comment "..."`

仓库信息无需硬编码，在本地仓库目录中执行时 `gh` 会基于 `git remote -v` 自动推断。

## 将 Pull Request 作为分诊来源

**是否将 PR 纳入分诊队列：否** *(若本项目希望将外部贡献者提交的 PR 视作需求提议统一处理，可将此处改为 `是`；`/triage` 技能会读取此配置)*。

当设为 `是` 时，PR 将沿用与 Issue 相同的标签与流转状态，使用对应的 `gh pr` 指令：

- **查看 PR**：`gh pr view <number> --comments`，并通过 `gh pr diff <number>` 查看改动差异。
- **列出待分诊的外部 PR**：`gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`，仅保留 `authorAssociation` 为 `CONTRIBUTOR`、`FIRST_TIME_CONTRIBUTOR` 或 `NONE` 的记录（排除仓库自身拥有者 `OWNER`、成员 `MEMBER` 或维护者 `COLLABORATOR`）。
- **评论 / 打标 / 关闭**：对应使用 `gh pr comment`、`gh pr edit --add-label`/`--remove-label`、`gh pr close`。

由于 GitHub 的 Issue 与 PR 共享同一编号空间，单纯的 `#42` 可能是 Issue 或 PR。建议优先执行 `gh pr view 42`，未命中时兜底回退为 `gh issue view 42`。

## 当技能提示 "publish to the issue tracker" 时

在 GitHub 上创建新的 Issue。

## 当技能提示 "fetch the relevant ticket" 时

执行 `gh issue view <number> --comments` 读取指定编号的内容与讨论。

## Wayfinding 导航与任务调度操作

供 `/wayfinder` 技能使用。**导航地图 (Map)** 表现为一个核心主 Issue，其下的各个 **子任务 (Child tickets)** 作为具体执行 Issue。

- **地图主 Issue (Map)**：一个带有 `wayfinder:map` 标签的独立 Issue，记录上下文备忘、当前已有决策 (Decisions-so-far) 与不确定区域 (Fog)。创建命令：`gh issue create --label wayfinder:map`。
- **子任务工单 (Child ticket)**：通过 GitHub sub-issue 关联至主地图 Issue。若仓库未开启 sub-issue 功能，则在地图正文的任务列表中列出该子任务，并在子任务正文顶部注明 `所属主任务: #<map>`。标签格式为：`wayfinder:<type>`（如 `research` / `prototype` / `grilling` / `task`）。一旦被认领，该工单将分配给对应执行者。
- **阻塞依赖关系 (Blocking)**：优先使用 GitHub 原生 Issue 依赖项机制。通过 API 关联依赖：`gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`（注意 `<blocker-db-id>` 是数据库全局数值 ID `gh api repos/<owner>/<repo>/issues/<n> --jq .id`，而非普通的 `#number`）。若不可用，则在子任务正文顶部书写 `前置阻塞: #<n>, #<n>`。当所有阻塞任务关闭后，该工单自动解锁。
- **任务就绪队列查询 (Frontier query)**：列出地图下未完成的子任务（`gh issue list --state open`，限定范围在子任务列表内），剔除存在未解前置阻塞或已被指派的任务；按地图顺序取首个就绪任务。
- **认领任务 (Claim)**：`gh issue edit <n> --add-assignee @me` 作为当前会话的第一个写入动作。
- **解决与闭环 (Resolve)**：`gh issue comment <n> --body "<方案与结论>"`，随后执行 `gh issue close <n>`，最后将决策结论摘要回填追加至地图主 Issue 的 Decisions-so-far 章节。
