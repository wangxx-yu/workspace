# context 模块

`src/context/` 负责从解析结果中整理出适合审查阶段消费的统一上下文。

## 组成

- `manager.py`: `CodeReviewContextManager`
- `history.py`: 历史状态读写

## CodeReviewContextManager

主要职责：
- 生成 `file_contexts`
- 生成 `structure_summary`
- 识别 `key_files`
- 计算 `dependency_focus_paths`
- 读取和生成 `incremental_state`
- 估算 `budget`
- 持久化历史 fingerprint

关键识别规则：
- `ENTRYPOINT_NAMES`: `main.py`、`app.py`、`manage.py`、`index.ts`、`index.js`
- `CONFIG_NAMES`: `pyproject.toml`、`package.json`、`tsconfig.json`、`requirements.txt`

关键文件的评分来源包括：
- 是否是入口文件
- 是否是配置文件
- 是否位于顶层目录
- 在依赖图中的连接度

## 历史状态

历史状态存储在 `history_file_path`，默认是仓库根目录下的 `.code-review-history.json`。存储结构记录：
- 文件路径
- 内容 hash
- 历史 issue fingerprint 列表

这些信息会驱动：
- 增量文件识别
- 默认只输出新增 issue 的反馈策略
