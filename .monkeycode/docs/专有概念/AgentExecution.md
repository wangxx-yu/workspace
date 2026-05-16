# AgentExecution

系统中的审查执行由 `ReviewExecutionService`、`TaskScheduler` 和 `CodeReviewErrorRecovery` 共同完成。

执行结构分为三层：

1. 计划层
- `CodeReviewPlan`
- `CodeReviewTask`

2. 调度层
- `TaskScheduler`
- `ReviewExecution`
- `TaskResult`

3. 恢复与反馈层
- `CodeReviewErrorRecovery`
- `CodeReviewFeedbackService`

完整模式下默认执行五个 task：
- `structure`
- `security`
- `style`
- `performance`
- `test`

summary 模式下默认执行三个 task：
- `structure`
- `security`
- `test`

恢复逻辑通过 `CircuitBreaker` 记录每个 agent 的连续失败次数。熔断打开后，调度层会把对应任务作为降级跳过事件记录到恢复摘要中。运行模式为 `apply_with_git` 且配置 `allow_apply_with_git=False` 时，恢复层会把有效模式降级为 `propose_patch`。

执行结束后，反馈层会：
- 汇总所有 task 的 issue
- 按历史 fingerprint 过滤旧问题
- 把 issue 回写到 `FileReviewContext.suggestions`
- 生成 `FeedbackSummary`
- 生成 `ReportSummary`
