# api-and-output 模块

这个模块组覆盖 API 暴露层、报告后处理层和格式化输出层。

## `src/api.py`

职责：
- 定义 FastAPI 应用工厂 `create_app()`
- 定义请求模型 `QueryRequestBase`、`AnalyzeRequest`、`AnalyzeSummaryRequest`
- 定义错误模型 `ErrorBody`、`ErrorResponse`
- 统一异常处理与 OpenAPI 示例
- 提供 `/health`、`/analyze`、`/analyze-formatted`、`/analyze-summary`

## `src/report_processing.py`

职责：
- `ReportQueryOptions`: 收敛过滤和裁剪参数
- `filter_report()`: 严重级、agent、路径、排序、分页
- `trim_report()`: 大字段裁剪
- `build_filtered_summary()`: 构造过滤后的 `ReportSummary`

这个模块是 CLI 与 API 的共享逻辑中心。

## `src/output/formatter.py`

职责：
- `to_json()`
- `to_markdown()`
- `to_sarif()`

Markdown 输出会串联：
- 仓库与文件统计
- parsed files
- dependency edges
- review context 摘要
- execution 摘要
- recovery 摘要
- feedback 摘要
- issues
- failed files

## `src/output/sarif.py`

职责：
- 构建 SARIF schema 顶层结构
- 从 issue 列表构建 rule 列表
- 将 issue 映射为 result

当前额外填充的信息包括：
- `helpUri`
- `rule.properties.severity`
- `result.properties.confidence`
- `result.properties.severity`
