# ReviewContext

`ReviewContext` 是审查阶段的核心输入模型，定义在 `src/common/schemas.py`。它承载从输入阶段提炼出的文件上下文、结构摘要、关键文件、依赖焦点、增量状态和预算信息。

字段组成：
- `repo_path`: 当前仓库绝对路径。
- `file_contexts`: 每个解析文件对应一个 `FileReviewContext`。
- `target_file_paths`: 当前轮次需要重点审查的目标文件列表。
- `structure_summary`: 仓库级结构摘要。
- `key_files`: 根据入口、配置、度数等规则识别的重要文件。
- `dependency_focus_paths`: 与关键文件存在依赖关系的关注路径。
- `incremental_state`: 新增、变更、未变更文件和历史 fingerprint。
- `budget`: 估算 token 预算和截断原因。

`CodeReviewContextManager.build()` 负责构建这个对象。它会先读取历史状态，再组合解析文件与依赖图，最后根据配置决定 `target_file_paths`。

summary 模式下会执行专门裁剪：
- `key_files` 置空
- `dependency_focus_paths` 置空
- `structure_summary.highlighted_paths` 置空

这样做的目标是降低上下文体积，同时保留 `file_contexts` 和 `incremental_state` 供 agent 做基础判断和历史去重。
