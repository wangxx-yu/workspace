# 用户指令记忆

本文件记录了用户的指令、偏好和教导，用于在未来的交互中提供参考。

## 格式

### 用户指令条目
用户指令条目应遵循以下格式：

[用户指令摘要]
- Date: [YYYY-MM-DD]
- Context: [提及的场景或时间]
- Instructions:
  - [用户教导或指示的内容，逐行描述]

### 项目知识条目
Agent 在任务执行过程中发现的条目应遵循以下格式：

[项目知识摘要]
- Date: [YYYY-MM-DD]
- Context: Agent 在执行 [具体任务描述] 时发现
- Category: [运维部署|构建方法|测试方法|排错调试|工作流协作|环境配置]
- Instructions:
  - [具体的知识点，逐行描述]

## 去重策略
- 添加新条目前，检查是否存在相似或相同的指令
- 若发现重复，跳过新条目或与已有条目合并
- 合并时，更新上下文或日期信息
- 这有助于避免冗余条目，保持记忆文件整洁

## 条目

[回复与执行约束]
- Date: 2026-05-16
- Context: 用户要求实现智能代码审查 Agent，并且当前项目规则要求统一输出与协作方式
- Instructions:
  - 所有回复使用简体中文。
  - 先检查仓库上下文，再做代码实现。
  - 优先做最小正确改动，并按阶段推进可测试交付物。

[项目启动阶段知识]
- Date: 2026-05-16
- Context: Agent 在执行阶段0与阶段1最小落地时发现
- Category: 构建方法
- Instructions:
  - 当前项目入口命令为 `python main.py --help`。
  - 当前最小验证命令为 `python main.py analyze --repo tests/fixtures/python_sample_repo --format json`。
  - 当前测试命令为 `pytest`。

[阶段2上下文与历史文件约束]
- Date: 2026-05-16
- Context: Agent 在执行阶段2上下文管理与增量审查基线时发现
- Category: 排错调试
- Instructions:
  - 审查历史文件默认写入仓库根目录的 `.code-review-history.json`。
  - 扫描阶段需要显式排除历史文件，避免把自身状态文件计入 `failed_files` 或上下文预算。
  - 涉及 fixture 的测试应隔离运行目录，避免历史文件污染首次审查断言。

[阶段3调度层知识]
- Date: 2026-05-16
- Context: Agent 在执行阶段3纯Python DAG 调度器时发现
- Category: 测试方法
- Instructions:
  - 阶段3的核心验证命令仍使用 `pytest`，其中 `tests/test_control.py` 负责覆盖 DAG 顺序、并发批次和失败隔离。
  - 当前任务默认顺序来自 `AppSettings.review_task_order`，依赖关系来自 `AppSettings.review_task_dependencies`。
  - 调度器输出统一写入 `Report.execution`，后续阶段的 Agent 执行结果应继续复用这份执行状态结构。

[阶段4审查Agent知识]
- Date: 2026-05-16
- Context: Agent 在执行阶段4五类审查 Agent 最小规则实现时发现
- Category: 测试方法
- Instructions:
  - `tests/test_agents.py` 负责覆盖 Structure、Security、Style 的核心规则检出。
  - 当前默认五类任务为 `structure`、`security`、`style`、`performance`、`test`，其中后四类依赖 `structure`。
  - `PerformanceAgent` 和 `TestAgent` 当前是最小可用实现，后续阶段可在保持统一接口的前提下逐步增强。

[阶段5恢复层知识]
- Date: 2026-05-16
- Context: Agent 在执行阶段5错误恢复、熔断与模式降级时发现
- Category: 测试方法
- Instructions:
  - `tests/test_recovery.py` 负责覆盖熔断器开启、降级执行和 `apply_with_git` 模式降级。
  - 恢复层统一写入 `Report.recovery`，后续阶段涉及重试、LLM 容错或补丁应用时应继续复用这份结构。
  - 当前 `apply_with_git` 默认通过 `allow_apply_with_git=false` 降级到 `propose_patch`。

[阶段6反馈层知识]
- Date: 2026-05-16
- Context: Agent 在执行阶段6反馈注入、增量目标过滤与自验证骨架时发现
- Category: 测试方法
- Instructions:
  - `tests/test_feedback.py` 负责覆盖 issue 回写到 `file_contexts`、目标文件范围和自验证结果摘要。
  - 反馈层统一写入 `Report.feedback`，后续阶段做测试结果注入、修复回路和增量 PR 审查时应继续复用这份结构。
  - 当前 `review_changed_files_only=true` 时优先使用 `incremental_state.new_or_changed_paths` 作为目标范围，若为空则回退到全文件集合。

[阶段7输出与API知识]
- Date: 2026-05-16
- Context: Agent 在执行阶段7报告输出、FastAPI 接口和最小 SARIF 集成时发现
- Category: 测试方法
- Instructions:
  - `tests/test_api.py` 负责覆盖 `/health` 和 `/analyze` 接口契约。
  - `tests/test_output.py` 负责覆盖最小 SARIF 输出结构。
  - 当前 CLI 支持 `json`、`markdown`、`sarif` 三种输出格式，服务入口为 `python main.py serve --host 0.0.0.0 --port 8000`。

[强化审查能力知识]
- Date: 2026-05-16
- Context: Agent 在执行核心审查能力强化时发现
- Category: 测试方法
- Instructions:
  - `tests/test_agents.py` 现在同时覆盖安全 AST 规则、结构复杂度与未引用 import、以及测试文件映射规则。
  - `SecurityAgent` 当前优先使用 AST 检测 `os.system`、`subprocess.* shell=True`、`eval/exec`、`pickle.load/loads`，硬编码密钥仍保留正则补充。
  - `StructureAgent` 当前已包含循环依赖、超长函数、分支复杂度和未引用 import 的启发式规则。

[性能与测试增强知识]
- Date: 2026-05-16
- Context: Agent 在执行 PerformanceAgent 与 TestAgent 强化时发现
- Category: 测试方法
- Instructions:
  - `PerformanceAgent` 当前已包含循环内 I/O 和循环内重复 `len()` 调用的 AST 启发式规则。
  - `TestAgent` 当前支持可选真实测试执行，执行结果通过 `TaskResult.evidence` 传入反馈层，并汇总到 `Report.feedback.test_summary`。
  - 默认 `test_execution_enabled=false`，开启后使用 `test_command` 与 `test_timeout_seconds` 控制测试执行行为。

[安全与结构二次强化知识]
- Date: 2026-05-16
- Context: Agent 在执行 SecurityAgent 与 StructureAgent 第二轮强化时发现
- Category: 测试方法
- Instructions:
  - `SecurityAgent` 当前额外覆盖 SQL 字符串拼接、`yaml.load` 非安全使用、`tempfile.mktemp` 和 `random.*` 弱随机启发式。
  - `StructureAgent` 当前额外覆盖未引用函数和未引用类的保守启发式，置信度保持在较低水平以体现结论保守性。
  - `tests/test_agents.py` 已覆盖这些新增规则，后续继续增强时应优先扩展该测试文件。

[误报收敛与参数覆盖知识]
- Date: 2026-05-16
- Context: Agent 在执行误报收敛与 API/CLI 参数扩展时发现
- Category: 测试方法
- Instructions:
  - `StructureAgent` 的未引用符号规则当前会避开单文件仓库中已在本文件内部引用的符号，以减少明显误报。
  - `TestAgent` 当前会跳过 `__init__.py` 的目标测试映射检查，以减少包初始化文件的噪声。
  - `/analyze` API 和 `main.py analyze` 当前支持按请求覆盖 `review_changed_files_only`、`test_execution_enabled`、`test_command`、`test_timeout_seconds`。

[Git URL 输入知识]
- Date: 2026-05-16
- Context: Agent 在执行阶段1远程仓库输入扩展时发现
- Category: 测试方法
- Instructions:
  - `RepoLoader` 当前支持本地路径和 Git URL，测试中使用 `file://` 仓库地址模拟浅克隆输入。
  - 远程克隆结果通过 `LoadedRepository` 返回，`InputPipeline` 会在 `finally` 中清理临时目录。
  - `tests/test_input_pipeline.py` 和 `tests/test_api.py` 已覆盖 `file://` Git 仓库输入与临时目录清理行为。

[克隆错误分类与API过滤知识]
- Date: 2026-05-16
- Context: Agent 在执行 Git 克隆超时分类与 API 输出过滤扩展时发现
- Category: 测试方法
- Instructions:
  - `RepoLoader` 当前使用 `subprocess.run` 调用 `git clone`，支持按 `git_clone_timeout_seconds` 抛出 `TimeoutError`。
  - `/analyze` 当前支持 `severity_filter` 与 `agent_filter`，用于在响应前过滤 issue 集合。
  - `/analyze-formatted` 当前支持直接返回 `json`、`markdown`、`sarif` 格式化内容，`tests/test_api.py` 已覆盖该能力。

[摘要与仅新增问题过滤知识]
- Date: 2026-05-16
- Context: Agent 在执行轻量 summary 输出与历史问题过滤增强时发现
- Category: 测试方法
- Instructions:
  - `Report.summary` 当前提供轻量统计视图，`/analyze-summary` 直接返回该结构。
  - 当 `report_only_new_issues=true` 时，反馈层会基于历史 `issue_fingerprints` 过滤已存在问题，仅保留新增 issue。
  - `tests/test_feedback.py` 已覆盖“第二次审查只返回新增问题”的行为，`tests/test_api.py` 已覆盖 summary 接口。

[API 排序分页与 GitHub URL 规范化知识]
- Date: 2026-05-16
- Context: Agent 在执行服务化增强与 API 过滤扩展时发现
- Category: 测试方法
- Instructions:
  - `RepoLoader.load()` 当前会将 `https://github.com/<owner>/<repo>` 规范化为追加 `.git` 的 clone 地址。
  - `/analyze`、`/analyze-formatted`、`/analyze-summary` 当前支持 `path_filter`、`sort_by`、`offset`、`limit`。
  - 涉及 issue 排序与分页的 API 测试应显式设置 `report_only_new_issues=False`，避免 fixture 历史 fingerprint 使结果集为空。

[clone 错误分类与响应裁剪知识]
- Date: 2026-05-16
- Context: Agent 在执行 API 服务化收尾增强时发现
- Category: 测试方法
- Instructions:
  - `RepoLoader` 当前会将 clone 失败分类为 `repository_not_found`、`permission_denied`、`network_error`、`invalid_reference`、`unknown`，并抛出 `RepoCloneError`。
  - API 会将 `RepoCloneError` 转成 `400` 响应，`detail` 中包含 `error=repo_clone_failed`、`category`、`message`。
  - `/analyze` 与 `/analyze-formatted` 当前支持通过 `include_parsed_files`、`include_project_graph`、`include_review_context`、`include_execution`、`include_feedback` 裁剪大响应字段。

[API 参数校验与 summary 路径知识]
- Date: 2026-05-16
- Context: Agent 在执行接口治理与轻量 summary 优化时发现
- Category: 测试方法
- Instructions:
  - `AnalyzeRequest.output_format` 当前限制为 `json|markdown|sarif`，`sort_by` 当前限制为 `severity|path`。
  - `AnalyzeRequest.offset >= 0`，`limit >= 1`，非法参数会由 FastAPI/Pydantic 直接返回 `422`。
  - `/analyze-summary` 当前会重新分析仓库后，直接基于 `_filter_report()` 的 issue 结果和 `CodeReviewFeedbackService.build_summary()` 构造 summary，而不走完整裁剪响应路径。

[统一错误响应与 CLI 对齐知识]
- Date: 2026-05-16
- Context: Agent 在执行 API 错误治理与 CLI 对齐扩展时发现
- Category: 测试方法
- Instructions:
  - API 当前统一返回 `{"error": {"code", "message", "details"}}` 结构，覆盖 `HTTPException`、`RequestValidationError` 和未捕获异常。
  - `repo_clone_failed` 当前通过统一错误包装返回，分类信息位于 `error.details.category`。
  - CLI `main.py analyze` 当前已支持 `--severity-filter`、`--agent-filter`、`--path-filter`、`--sort-by`、`--offset`、`--limit`、`--summary`，并复用 API 层过滤与 summary 构造逻辑。

[共享报告处理与文档对齐知识]
- Date: 2026-05-16
- Context: Agent 在执行 CLI/API 共享逻辑收口与 README 同步时发现
- Category: 测试方法
- Instructions:
  - 共享报告处理逻辑当前集中在 `src/report_processing.py`，包含 `ReportQueryOptions`、`filter_report()`、`trim_report()`、`build_filtered_summary()`。
  - `main.py` 与 `src/api.py` 当前都应通过 `src/report_processing.py` 复用过滤、裁剪与 summary 构造逻辑。
  - `README.md` 当前已同步 CLI 过滤分页、summary、API 响应裁剪、格式化接口和统一错误响应结构，新增接口能力后应优先保持文档同步。

[OpenAPI 文档与请求模型拆分知识]
- Date: 2026-05-16
- Context: Agent 在执行 OpenAPI 文档细化与 summary 请求模型拆分时发现
- Category: 测试方法
- Instructions:
  - `src/api.py` 当前使用 `QueryRequestBase`、`AnalyzeRequest`、`AnalyzeSummaryRequest` 分离完整分析请求与 summary 请求文档。
  - OpenAPI 当前为 `/analyze`、`/analyze-formatted`、`/analyze-summary` 显式声明了 `400/422/500` 统一错误响应示例。
  - `tests/test_api.py` 当前覆盖 `/openapi.json`，验证错误示例与 `AnalyzeSummaryRequest` schema 已正确暴露。

[summary 轻量执行路径知识]
- Date: 2026-05-16
- Context: Agent 在执行真正的 summary 轻量模式收口时发现
- Category: 测试方法
- Instructions:
  - `InputPipeline.analyze()` 当前支持 `summary_only=True`，该模式会裁剪 `parsed_files`、`project_graph`、`execution`、`recovery`、`feedback`，仅保留 summary 所需核心结果。
  - `ReviewExecutionService.execute()` 当前支持 `summary_only=True`，会跳过 `feedback.build_feedback()` 和 `recovery.build_summary()`，并避免将 issue 列表注入每个 `file_context.issues`。
  - `/analyze-summary` 当前必须调用 `InputPipeline(...).analyze(repo_ref, summary_only=True)`，`tests/test_api.py` 与 `tests/test_input_pipeline.py` 已覆盖这条轻量链路。

[summary 无 review_context 构造知识]
- Date: 2026-05-16
- Context: Agent 在执行轻量 summary 再压缩时发现
- Category: 测试方法
- Instructions:
  - `InputPipeline` 的 `summary_only=True` 当前会进一步将返回的 `report.review_context` 置为 `None`，减少 summary 响应中的大对象驻留。
  - `build_filtered_summary()` 当前优先使用 `report.review_context` 构造 summary；若其为空，则回退到 `report.summary + filtered issues` 重新计算 `severity_counts` 和 `agent_counts`。
  - `tests/test_report_processing.py` 当前覆盖“无 `review_context` 仍可构造 summary”的行为。

[轻量上下文构建知识]
- Date: 2026-05-16
- Context: Agent 在执行 summary 轻量模式前置到上下文层时发现
- Category: 测试方法
- Instructions:
  - `CodeReviewContextManager.build(..., summary_only=True)` 当前会清空 `key_files`、`dependency_focus_paths`，并将 `structure_summary.highlighted_paths` 置空，以减少 summary 路径中的非必要上下文字段。
  - 轻量上下文模式仍然保留 `file_contexts`、`incremental_state`、`target_file_paths` 和 `budget`，因为现有 agent 与历史去重仍依赖这些字段。
  - `tests/test_input_pipeline.py` 当前覆盖了 summary 上下文模式对 `key_files`、`dependency_focus_paths` 和 `highlighted_paths` 的裁剪行为。

[summary 历史持久化上下文压缩知识]
- Date: 2026-05-16
- Context: Agent 在执行 summary 链路尾段内存压缩时发现
- Category: 测试方法
- Instructions:
  - `InputPipeline` 在 `summary_only=True` 时，当前会先将 `review_context.file_contexts` 压缩为仅保留 `path`、`language`、`content_hash`、`size_bytes`、`suggestions`，再调用 `persist_history()`。
  - 该压缩路径通过 `InputPipeline._compress_history_context()` 实现，目标是减少 summary 路径尾段的大对象驻留，同时保持历史 fingerprint 持久化所需信息完整。
  - `tests/test_input_pipeline.py` 当前覆盖了压缩后的持久化上下文中 `functions/classes/dependencies` 为空且 `suggestions` 仍存在的行为。

[summary 轻量 agent 集知识]
- Date: 2026-05-16
- Context: Agent 在执行 summary 路径 CPU 侧优化时发现
- Category: 测试方法
- Instructions:
  - `AppSettings` 当前提供 `summary_task_order` 和 `summary_task_dependencies`，默认只运行 `structure`、`security`、`test` 三类任务。
  - `ReviewExecutionService._build_plan(summary_only=True)` 当前会基于 `summary_task_order` / `summary_task_dependencies` 构造轻量执行计划，避免在 summary 路径运行 `style` 和 `performance`。
  - `tests/test_control.py` 与 `tests/test_api.py` 当前分别覆盖 summary 执行计划和 summary 接口只产出轻量 agent 集统计的行为。

[agent 文件内容与 AST 共享缓存知识]
- Date: 2026-05-16
- Context: Agent 在执行完整分析与 summary 分析共用 CPU 优化时发现
- Category: 测试方法
- Instructions:
  - `BaseReviewAgent` 当前内置 `_read_file_content()` 和 `_parse_python_ast()` 共享缓存，缓存键为 `(repo_path, file_path, content_hash)`。
  - `StructureAgent`、`SecurityAgent`、`PerformanceAgent` 当前都应通过基类缓存方法复用文件内容和 Python AST，避免重复 `read_text()` 与 `ast.parse()`。
  - `tests/test_agents.py` 当前覆盖“多个 agent 共享缓存后 AST 解析次数受控”的行为。

[输入解析期预热缓存知识]
- Date: 2026-05-16
- Context: Agent 在执行输入层到 agent 层全链路 AST 复用时发现
- Category: 测试方法
- Instructions:
  - `CodeParser.parse()` 当前会在读取文件内容并计算 `content_hash` 后，调用 `BaseReviewAgent.warm_file_cache()` 预热文件内容缓存。
  - 对 Python 文件，`CodeParser._parse_python()` 当前会在首次 `ast.parse()` 后调用 `BaseReviewAgent.warm_ast_cache()`，让后续 agent 首次运行也直接命中 AST 缓存。
  - `tests/test_agents.py` 当前已将共享 AST 解析次数断言收紧到 `== 1`，确保整条分析链路对 Python 文件只做一次 AST 解析。

[共享缓存生命周期知识]
- Date: 2026-05-16
- Context: Agent 在执行长生命周期 API 进程缓存治理时发现
- Category: 测试方法
- Instructions:
  - `BaseReviewAgent` 当前提供 `clear_repo_cache(repo_path)`，按仓库维度清理 `_content_cache` 与 `_ast_cache` 的旧条目。
  - `InputPipeline.analyze()` 当前会在每次分析开始时调用 `BaseReviewAgent.clear_repo_cache(str(repo_path))`，避免同一 API 进程长期累积目标仓库的陈旧缓存。
  - `tests/test_agents.py` 当前覆盖了“分析前会清理该仓库旧缓存条目”的行为。

[共享缓存有界策略知识]
- Date: 2026-05-16
- Context: Agent 在执行长期在线运行内存治理时发现
- Category: 测试方法
- Instructions:
  - `AppSettings` 当前提供 `agent_cache_max_entries`，默认值为 `2000`，用于约束共享内容缓存和 AST 缓存的条目数。
  - `BaseReviewAgent` 当前使用 `OrderedDict` 维护 `_content_cache` 和 `_ast_cache`，在读写和预热时会 `move_to_end()`，并通过 `_enforce_cache_bounds()` 执行近似 LRU 淘汰。
  - `tests/test_agents.py` 当前覆盖了缓存条目数超过上限后最旧条目被淘汰的行为。

[缓存与执行指标知识]
- Date: 2026-05-16
- Context: Agent 在执行可观测性增强时发现
- Category: 测试方法
- Instructions:
  - `ReportMetadata` 当前包含 `cache_content_hits`、`cache_content_misses`、`cache_ast_hits`、`cache_ast_misses`、`executed_agents` 字段，用于暴露一次分析中的缓存与执行指标。
  - `BaseReviewAgent` 当前通过基类级别计数器统一累计缓存命中与未命中次数，`InputPipeline.analyze()` 会在分析开始时 `reset_cache_metrics()`，在生成 `ReportMetadata` 时读取这些指标。
  - `tests/test_agents.py` 当前覆盖了元数据中缓存指标和 `executed_agents` 输出的行为。

[summary metrics 暴露知识]
- Date: 2026-05-16
- Context: Agent 在执行轻量摘要可观测性补齐时发现
- Category: 测试方法
- Instructions:
  - `ReportSummary` 当前包含 `metrics` 字段，暴露 `cache_content_hits`、`cache_content_misses`、`cache_ast_hits`、`cache_ast_misses`、`executed_agents`。
  - `InputPipeline` 在生成 `report.summary` 后会把 `ReportMetadata` 中的缓存与执行指标同步写入 `summary.metrics`。
  - `build_filtered_summary()` 当前在重建 summary 时必须保留原始 `report.summary.metrics`，`tests/test_report_processing.py`、`tests/test_api.py`、`tests/test_main.py` 已覆盖该行为。

[CLI summary 轻量路径一致性知识]
- Date: 2026-05-16
- Context: Agent 在执行最终结果收口时发现
- Category: 测试方法
- Instructions:
  - `main.py analyze --summary` 当前必须调用 `InputPipeline(...).analyze(repo_ref, summary_only=True)`，与 `/analyze-summary` 使用相同的轻量执行路径。
  - CLI summary 当前输出的 `metrics.executed_agents` 应为轻量 agent 集 `['structure', 'security', 'test']`，`tests/test_main.py` 已覆盖该行为。
