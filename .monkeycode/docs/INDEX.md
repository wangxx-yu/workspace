# Code Review Agent 文档

## 项目概述

Code Review Agent 是一个面向代码仓库的静态审查服务，提供 CLI 和 FastAPI 两种入口。它围绕统一的 `Report` 数据契约组织扫描、解析、上下文构建、并发审查、恢复、反馈和多格式输出，当前重点支持 Python 仓库。

系统支持本地目录、Git URL、GitHub HTTPS URL 作为输入源。对远程仓库会执行浅克隆，并在分析结束后清理临时目录。完整分析路径会返回结构化上下文、执行过程、恢复信息和反馈摘要，轻量 summary 路径会返回压缩后的问题统计和执行指标。

当前审查链路由五类 agent 组成：`structure`、`security`、`style`、`performance`、`test`。其中 summary 模式默认只运行 `structure`、`security`、`test`，以降低 CPU 开销和响应体积。

## 文档导航

- [架构文档](./ARCHITECTURE.md): 系统目标、模块边界、执行流程和关键设计决策。
- [接口文档](./INTERFACES.md): CLI 参数、HTTP API、输入输出契约与错误模型。
- [开发者指南](./DEVELOPER_GUIDE.md): 环境搭建、运行方式、测试方法和开发注意事项。
- [专有概念 / ReviewContext](./专有概念/ReviewContext.md): 审查上下文、预算与增量状态。
- [专有概念 / Report](./专有概念/Report.md): 统一报告模型与 summary 视图。
- [专有概念 / AgentExecution](./专有概念/AgentExecution.md): DAG 调度、恢复与反馈回写。
- [模块 / input](./模块/input.md): 仓库加载、扫描、解析、依赖提取、输入编排。
- [模块 / context](./模块/context.md): 上下文构建、关键文件识别、历史状态管理。
- [模块 / control](./模块/control.md): 任务计划、调度与 agent 执行服务。
- [模块 / agents](./模块/agents.md): 各审查 agent 的职责与规则范围。
- [模块 / api-and-output](./模块/api-and-output.md): FastAPI 暴露层与 JSON/Markdown/SARIF 输出。
