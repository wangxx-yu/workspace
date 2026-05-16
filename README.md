# Code Review Agent

一个按阶段实现的智能代码审查 Agent。

仓库地址：`https://github.com/wangxx-yu/workspace`

## 项目文档

完整项目文档位于 `.monkeycode/docs/`：

- `INDEX.md`: 文档索引
- `ARCHITECTURE.md`: 系统架构、模块边界、执行流程
- `INTERFACES.md`: CLI、HTTP API、错误模型、SARIF
- `DEVELOPER_GUIDE.md`: 环境搭建、运行方式、测试方法
- `专有概念/`: `Report`、`ReviewContext`、执行模型等核心概念
- `模块/`: `input`、`context`、`control`、`agents`、`api-and-output` 模块说明

当前已落地的范围：

- 阶段 0：项目骨架、配置、日志、CLI 入口
- 阶段 1：本地仓库扫描、文件过滤、Python 结构化解析、静态依赖图输出
- 阶段 2：文件上下文、结构摘要、关键文件识别、历史去重与增量状态
- 阶段 3：纯 Python DAG 调度、并发执行、失败隔离
- 阶段 4：五类审查 Agent 最小规则实现
- 阶段 5：错误恢复、熔断与模式降级
- 阶段 6：反馈注入、目标范围过滤与自验证骨架
- 阶段 7：Markdown/JSON/SARIF 输出、FastAPI 接口、健康检查、过滤分页、summary 与统一错误响应

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
python main.py --help
python main.py analyze --repo tests/fixtures/python_sample_repo --format json
python main.py analyze --repo tests/fixtures/python_sample_repo --format sarif
python main.py serve --host 0.0.0.0 --port 8000
```

## 当前限制

- 结构化解析当前优先支持 Python
- 远程仓库当前优先支持 Git URL 与 GitHub HTTPS URL
- 其他语言以文本模式记录，`parse_mode=text`

## 输出

CLI `analyze` 命令会输出统一数据契约：

- `parsed_files`
- `project_graph`
- `failed_files`
- `metadata`
- `review_context`
- `execution`
- `recovery`
- `feedback`

`review_context` 当前包含：

- `file_contexts`
- `structure_summary`
- `key_files`
- `dependency_focus_paths`
- `incremental_state`
- `budget`

可选格式：`json`、`markdown`、`sarif`。

## CLI

基础分析：

```bash
python main.py analyze --repo tests/fixtures/python_sample_repo --format json
```

SARIF 输出：

```bash
python main.py analyze --repo tests/fixtures/python_sample_repo --format sarif
```

只看 summary：

```bash
python main.py analyze --repo tests/fixtures/python_sample_repo --summary
```

过滤、排序、分页：

```bash
python main.py analyze \
  --repo tests/fixtures/python_sample_repo \
  --severity-filter low \
  --agent-filter test \
  --path-filter app/service.py \
  --sort-by path \
  --offset 0 \
  --limit 10
```

## API

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

分析接口：

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_ref":"tests/fixtures/python_sample_repo"}'
```

带过滤、排序、分页和响应裁剪：

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo_ref": "tests/fixtures/python_sample_repo",
    "severity_filter": ["low"],
    "agent_filter": ["test"],
    "path_filter": ["app/service.py"],
    "sort_by": "path",
    "offset": 0,
    "limit": 10,
    "include_parsed_files": false,
    "include_project_graph": false
  }'
```

summary 接口：

```bash
curl -X POST http://127.0.0.1:8000/analyze-summary \
  -H "Content-Type: application/json" \
  -d '{"repo_ref":"tests/fixtures/python_sample_repo","severity_filter":["low"]}'
```

格式化输出接口：

```bash
curl -X POST http://127.0.0.1:8000/analyze-formatted \
  -H "Content-Type: application/json" \
  -d '{"repo_ref":"tests/fixtures/python_sample_repo","output_format":"sarif"}'
```

统一错误响应结构：

```json
{
  "error": {
    "code": "validation_error",
    "message": "request validation failed",
    "details": []
  }
}
```

当前常见错误码：

- `repo_clone_failed`
- `validation_error`
- `internal_error`

## SARIF

CLI 和 API 都支持 SARIF 输出：

```bash
python main.py analyze --repo tests/fixtures/python_sample_repo --format sarif
```
