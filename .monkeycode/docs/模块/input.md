# input 模块

`src/input/` 负责把仓库引用转成可供审查的结构化输入。

## 组成

- `repo_loader.py`: 识别本地路径和 Git 仓库引用，处理浅克隆与临时目录清理。
- `scanner.py`: 根据 glob、文件数和体积预算筛选文件。
- `parser.py`: 解析扫描结果，当前重点支持 Python AST。
- `dependency_extractor.py`: 基于解析结果构建文件级依赖图。
- `models.py`: 输入阶段使用的中间模型。
- `service.py`: `InputPipeline` 主流程。

## 关键流程

`InputPipeline.analyze()` 会依次执行：
1. `RepoLoader.load()`
2. `RepositoryScanner.scan()`
3. `CodeParser.parse()`
4. `DependencyExtractor.build_graph()`
5. `CodeReviewContextManager.build()`
6. `ReviewExecutionService.execute()`
7. `persist_history()`
8. 组装 `Report`

## RepoLoader

`RepoLoader` 支持：
- 本地目录
- `https://` / `http://`
- `git@`
- `ssh://`
- `file://`

GitHub HTTPS URL 会在缺少 `.git` 后缀时自动补齐。远程仓库通过 `git clone --depth <n>` 执行浅克隆，超时时间来自 `git_clone_timeout_seconds`。

失败会抛出 `RepoCloneError`，当前分类包括：
- `repository_not_found`
- `permission_denied`
- `network_error`
- `invalid_reference`
- `unknown`

## InputPipeline

`InputPipeline` 还负责两项横切逻辑：
- 分析前设置和清理共享缓存
- 在 summary 模式下压缩历史持久化上下文

summary 模式持久化时只保留压缩后的 `FileReviewContext` 核心字段，避免历史文件过大。
