# agents 模块

`src/agents/` 提供具体审查规则实现。

## 公共基类

`base.py` 中的 `BaseReviewAgent` 提供：
- 文件内容读取缓存
- Python AST 解析缓存
- 缓存命中统计
- 仓库级缓存清理
- 全局条目上限控制

缓存键使用 `(repo_path, file_path, content_hash)`，保证同一文件不同内容版本可区分。

## StructureAgent

关注代码结构风险，当前规则包括：
- 循环依赖
- 超长函数
- 分支复杂度
- 未引用 import
- 未引用函数或类的启发式识别

## SecurityAgent

重点使用 Python AST 做保守静态检测，当前覆盖：
- `os.system`
- `subprocess.*` 且 `shell=True`
- `eval` / `exec`
- `pickle.load` / `pickle.loads`
- SQL 拼接
- `yaml.load`
- `tempfile.mktemp`
- `random.*`

## StyleAgent

关注风格与可读性阈值，例如：
- 函数长度
- 参数数量

## PerformanceAgent

关注常见性能异味，当前规则包括：
- `performance.loop-io`
- `performance.repeated-len-call`
- `performance.context-budget`

## TestAgent

负责测试相关推断和可选测试执行：
- 推导目标测试文件
- 根据配置决定是否执行测试命令
- 将执行结果写入 `TaskResult.evidence`
- 汇总到 `FeedbackSummary.test_summary`

当前实现对 `__init__.py` 做了跳过处理，避免误报测试缺失类结论。
