# 接口文档

## CLI

CLI 入口位于 `main.py`，包含 `analyze` 和 `serve` 两个子命令。

### `analyze`

用途：对本地仓库路径执行完整分析或 summary 分析。

核心参数：
- `--repo`: 仓库路径。
- `--format`: `json`、`markdown`、`sarif`。
- `--review-changed-files-only`: `true` 或 `false`，覆盖配置中的增量审查开关。
- `--test-execution-enabled`: `true` 或 `false`，控制 `TestAgent` 是否执行测试命令。
- `--test-command`: 自定义测试命令。
- `--test-timeout-seconds`: 测试命令超时秒数。
- `--severity-filter`: 可重复传入，按严重级过滤。
- `--agent-filter`: 可重复传入，按 agent 前缀过滤。
- `--path-filter`: 可重复传入，按文件路径过滤。
- `--sort-by`: `severity` 或 `path`。
- `--offset`: 分页起始偏移。
- `--limit`: 分页上限。
- `--summary`: 启用轻量 summary 路径。

执行语义：
- 普通模式调用 `InputPipeline(settings).analyze(args.repo, summary_only=False)`。
- summary 模式调用 `InputPipeline(settings).analyze(args.repo, summary_only=True)`，然后输出 `ReportSummary` JSON。
- 过滤、排序、分页和字段裁剪逻辑由 `src/report_processing.py` 统一实现。

### `serve`

用途：启动 FastAPI 服务。

参数：
- `--host`: 服务监听地址。
- `--port`: 服务端口。

运行时会调用 `create_app(settings)` 创建应用，并交由 `uvicorn.run()` 启动。

## HTTP API

FastAPI 应用定义在 `src/api.py`。

### `GET /health`

用途：健康检查。

响应：

```json
{
  "status": "ok"
}
```

### `POST /analyze`

用途：执行完整分析，返回结构化 `Report`。

请求模型：`AnalyzeRequest`

字段：
- `repo_ref`: 本地仓库路径、Git URL 或 GitHub HTTPS URL。
- `review_changed_files_only`
- `test_execution_enabled`
- `test_command`
- `test_timeout_seconds`
- `severity_filter`
- `agent_filter`
- `path_filter`
- `sort_by`: `severity | path`
- `offset >= 0`
- `limit >= 1`
- `output_format`: `json | markdown | sarif`，仅用于格式化接口。
- `include_parsed_files`
- `include_project_graph`
- `include_review_context`
- `include_execution`
- `include_feedback`

响应模型：`Report`

处理流程：
1. `_override_settings()` 用请求参数覆盖部分运行配置。
2. `_analyze_report()` 调用 `InputPipeline.analyze()` 产出报告。
3. `filter_report()` 和 `trim_report()` 应用过滤和字段裁剪。

### `POST /analyze-formatted`

用途：执行完整分析，并返回字符串格式内容。

响应结构：

```json
{
  "format": "sarif",
  "content": "..."
}
```

`content` 由 `ReportFormatter` 生成，支持 `json`、`markdown`、`sarif`。

### `POST /analyze-summary`

用途：执行轻量摘要分析，返回 `ReportSummary`。

请求模型：`AnalyzeSummaryRequest`

响应模型：`ReportSummary`

处理流程：
1. 覆盖请求级配置。
2. 调用 `InputPipeline(...).analyze(repo_ref, summary_only=True)`。
3. 通过 `build_filtered_summary()` 生成过滤后的摘要。

## 统一错误响应

所有 API 错误都映射为：

```json
{
  "error": {
    "code": "validation_error",
    "message": "request validation failed",
    "details": []
  }
}
```

当前显式覆盖的错误类型：
- `repo_clone_failed`: 远程克隆失败。
- `validation_error`: 请求参数校验失败。
- `internal_error`: 未捕获异常。

`RepoCloneError` 会额外返回：
- `details.category`
- `details.repo_ref`

## 输入与输出模型

### 核心输入

`repo_ref` 支持三类来源：
- 本地目录路径
- Git URL，例如 `git@...`、`ssh://...`、`file://...`
- GitHub HTTPS URL，若缺少 `.git` 后缀会自动补齐

### 核心输出

`Report` 由以下字段组成：
- `parsed_files`
- `project_graph`
- `failed_files`
- `issues`
- `metadata`
- `review_context`
- `execution`
- `recovery`
- `feedback`
- `summary`

`ReportSummary` 聚合以下内容：
- `repo_path`
- `total_issues`
- `total_files_parsed`
- `target_files`
- `severity_counts`
- `agent_counts`
- `metrics`

## SARIF

SARIF 由 `src/output/sarif.py` 生成，符合 2.1.0 schema。

规则映射：
- `critical` / `high` -> `error`
- `medium` -> `warning`
- `low` -> `note`

结果中会包含：
- `ruleId`
- `message.text`
- `properties.confidence`
- `properties.severity`
- `locations[].physicalLocation.artifactLocation.uri`
- `locations[].physicalLocation.region.startLine`
