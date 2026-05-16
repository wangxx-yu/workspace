# control 模块

`src/control/` 负责把多个审查 agent 组织为可调度的 DAG，并执行并发调度。

## 组成

- `plan.py`: 定义 `CodeReviewTask` 与 `CodeReviewPlan`
- `scheduler.py`: 调度与执行
- `service.py`: `ReviewExecutionService`

## ReviewExecutionService

它是控制层的主入口，负责：
- 构建 agent 实例集合
- 基于配置选择完整模式或 summary 模式任务集
- 创建 `CodeReviewPlan`
- 调用 `TaskScheduler.run()`
- 汇总 issues
- 调用反馈层生成 `FeedbackSummary` 和 `ReportSummary`

## 任务依赖

默认完整模式依赖：
- `structure`: 无依赖
- `security`: 依赖 `structure`
- `style`: 依赖 `structure`
- `performance`: 依赖 `structure`
- `test`: 依赖 `structure`

默认 summary 模式依赖：
- `structure`: 无依赖
- `security`: 依赖 `structure`
- `test`: 依赖 `structure`

## 调度输出

调度结果收敛到 `ReviewExecution`：
- `ready_order`
- `completed_order`
- `failed_tasks`
- `task_results`
- `progress`

每个 `TaskResult` 会记录：
- task 与 agent 名称
- 状态
- 依赖列表
- issues
- evidence
- error
- duration_ms
- recovery_action
- degraded
