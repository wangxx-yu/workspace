# Report

`Report` 是系统的统一输出模型，定义在 `src/common/schemas.py`。无论来源是 CLI 还是 API，最终都会收敛到这个结构或它的轻量摘要 `ReportSummary`。

`Report` 主要包含三类信息：

1. 输入产物
- `parsed_files`
- `project_graph`
- `failed_files`

2. 审查产物
- `issues`
- `review_context`
- `execution`
- `recovery`
- `feedback`

3. 元信息
- `metadata`
- `summary`

`ReportMetadata` 会记录仓库路径、扫描/解析数量，以及缓存命中和执行 agent 列表等运行指标。`ReportSummary` 聚合问题总数、严重级分布、agent 分布、目标文件列表和执行指标，适合做快速展示、统计或平台汇总。

summary 路径下的 `Report` 会做几项裁剪：
- `parsed_files` 为空列表
- `project_graph` 为空图
- `review_context` 为 `None`
- `execution` 为 `None`
- `recovery` 为 `None`
- `feedback` 为 `None`

同时 `summary` 字段仍然会保留聚合结果，供 CLI `--summary` 和 `/analyze-summary` 使用。
