# 开发者指南

## 项目目的

这个项目用于把代码仓库分析流程收敛为统一、可测试、可服务化的 Python 审查系统。它同时提供命令行入口和 HTTP 接口，适合作为本地工具、服务端能力或后续平台集成的基础。

核心职责：
- 读取仓库并生成结构化上下文。
- 并发执行多个审查 agent。
- 输出统一报告与轻量摘要。

## 环境要求

- Python 3
- `pip`
- `git`

如果需要执行测试类审查，还需要本地测试命令可运行，例如 `pytest`。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
python main.py --help
```

## 常用命令

完整分析：

```bash
python main.py analyze --repo tests/fixtures/python_sample_repo --format json
```

SARIF 输出：

```bash
python main.py analyze --repo tests/fixtures/python_sample_repo --format sarif
```

summary 输出：

```bash
python main.py analyze --repo tests/fixtures/python_sample_repo --summary
```

启动 API：

```bash
python main.py serve --host 0.0.0.0 --port 8000
```

运行测试：

```bash
python3 -m pytest
```

## 配置方式

配置由 `src/common/settings.py` 中的 `AppSettings` 定义，并使用 `CODE_REVIEW_AGENT_` 作为环境变量前缀。`.env` 文件会被自动加载。

关键配置项：
- 扫描范围：`include_globs`、`exclude_globs`
- 文件与体积预算：`max_files`、`max_file_bytes`、`max_total_bytes`
- 结构与风格阈值：`structure_max_function_lines`、`structure_max_branch_nodes`、`style_max_function_lines`、`style_max_parameters`
- 恢复：`circuit_breaker_failure_threshold`、`circuit_breaker_reset_seconds`
- 历史：`history_max_entries`、`history_file_path`
- 测试：`test_command`、`test_timeout_seconds`、`test_execution_enabled`
- 缓存：`agent_cache_max_entries`
- 远程仓库：`git_clone_timeout_seconds`、`git_shallow_clone_depth`、`temp_repo_parent_dir`
- API：`api_host`、`api_port`
- 任务编排：`review_task_order`、`review_task_dependencies`、`summary_task_order`、`summary_task_dependencies`

`config/default.json` 还提供了一份默认配置样例，包含扫描 glob、文件预算、模型与输出格式等字段。

## 开发流程建议

1. 从 `main.py`、`src/api.py`、`src/input/service.py` 开始理解主流程。
2. 修改规则时优先查看对应 agent 和 `tests/test_agents.py`。
3. 修改报告输出或过滤逻辑时同步查看 `src/report_processing.py`、`src/output/` 和对应测试。
4. 修改 summary 路径时同步验证 CLI 与 API 的语义一致性。

## 测试分层

- `tests/test_input_pipeline.py`: 输入编排、远程仓库、summary 裁剪、历史持久化。
- `tests/test_control.py`: DAG 顺序、依赖与 summary 任务集。
- `tests/test_agents.py`: 各 agent 规则与缓存行为。
- `tests/test_feedback.py`: 去重、回写、验证摘要。
- `tests/test_api.py`: HTTP 合约、统一错误响应、过滤/分页、summary。
- `tests/test_main.py`: CLI 输出与命令参数行为。
- `tests/test_output.py`: SARIF 与格式化输出。
- `tests/test_recovery.py`: 熔断、降级与恢复行为。
- `tests/test_report_processing.py`: 过滤、裁剪、summary 重建。

## 开发注意事项

### 统一复用 `report_processing`
CLI 与 API 共用 `ReportQueryOptions`、`filter_report()`、`trim_report()`、`build_filtered_summary()`。修改过滤和裁剪逻辑时应保持这一层为唯一实现点。

### 保护 summary 轻量路径
`summary_only=True` 是有意设计的性能路径。新增字段或行为时，需要判断它是否属于轻量路径，并同步评估：
- 是否需要出现在 `ReportSummary`
- 是否会增大 `review_context`
- 是否会触发额外 agent 开销

### 关注缓存生命周期
共享缓存位于 `BaseReviewAgent`。新增读取逻辑时优先复用缓存接口，并维持按仓库清理和全局上限机制。

### 保持历史去重语义稳定
历史问题过滤依赖 issue fingerprint。若修改 title、描述或 fingerprint 规则，需要同步评估已有历史记录和测试用例。

## 手工验证建议

修改后建议至少执行以下验证：

```bash
python3 -m pytest
python3 main.py analyze --repo tests/fixtures/python_sample_repo --summary
python3 main.py serve --host 0.0.0.0 --port 8000
```
