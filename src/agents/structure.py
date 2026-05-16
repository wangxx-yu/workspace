from __future__ import annotations

import ast
from pathlib import Path

from src.agents.base import BaseReviewAgent
from src.common.schemas import AgentReport, Issue, ReviewContext


BRANCH_NODE_TYPES = (ast.If, ast.For, ast.While, ast.Try, ast.Match)


class StructureAgent(BaseReviewAgent):
    agent_name = "structure"

    def __init__(self, max_function_lines: int = 40, max_branch_nodes: int = 8) -> None:
        self.max_function_lines = max_function_lines
        self.max_branch_nodes = max_branch_nodes

    def run(self, context: ReviewContext) -> AgentReport:
        issues: list[Issue] = []
        issues.extend(self._detect_cycles(context))
        issues.extend(self._detect_large_functions(context))
        issues.extend(self._detect_branch_heavy_functions(context))
        issues.extend(self._detect_unused_imports(context))
        issues.extend(self._detect_unused_symbols(context))

        if len(context.file_contexts) > 20:
            issues.append(
                Issue(
                    rule_id="structure.large-review-scope",
                    title="Review scope is large",
                    description="The repository slice contains more than 20 files and may need stronger summarization.",
                    severity="low",
                    path=context.file_contexts[0].path,
                    confidence=0.9,
                    evidence=[f"file_count={len(context.file_contexts)}"],
                )
            )

        return AgentReport(
            agent_name=self.agent_name,
            issues=issues,
            evidence=[f"key_files={len(context.key_files)}", f"focus_paths={len(context.dependency_focus_paths)}"],
            severity="info" if not issues else "low",
        )

    def _detect_cycles(self, context: ReviewContext) -> list[Issue]:
        graph = {
            item.path: [dependency for dependency in item.dependencies if dependency in {node.path for node in context.file_contexts}]
            for item in context.file_contexts
        }
        visited: set[str] = set()
        active: list[str] = []
        cycle_issues: list[Issue] = []
        recorded: set[tuple[str, ...]] = set()

        def visit(node: str) -> None:
            if node in active:
                cycle = active[active.index(node) :] + [node]
                normalized = tuple(cycle)
                if normalized not in recorded:
                    recorded.add(normalized)
                    cycle_issues.append(
                        Issue(
                            rule_id="structure.circular-dependency",
                            title="Circular dependency detected",
                            description="Static import analysis found a dependency cycle across files.",
                            severity="medium",
                            path=node,
                            confidence=0.85,
                            evidence=[" -> ".join(cycle)],
                        )
                    )
                return
            if node in visited:
                return

            visited.add(node)
            active.append(node)
            for dependency in graph.get(node, []):
                visit(dependency)
            active.pop()

        for node in graph:
            visit(node)

        return cycle_issues

    def _detect_large_functions(self, context: ReviewContext) -> list[Issue]:
        issues: list[Issue] = []
        for file_context in context.file_contexts:
            for function in file_context.functions:
                function_length = function.line_end - function.line_start + 1
                if function_length > self.max_function_lines:
                    issues.append(
                        Issue(
                            rule_id="structure.large-function",
                            title="Function is too large",
                            description="Function length exceeds the current structure threshold.",
                            severity="low",
                            path=file_context.path,
                            line=function.line_start,
                            confidence=0.95,
                            evidence=[f"function={function.name}", f"line_span={function_length}"],
                        )
                    )
        return issues

    def _detect_branch_heavy_functions(self, context: ReviewContext) -> list[Issue]:
        issues: list[Issue] = []
        for file_context in context.file_contexts:
            if file_context.language != "python":
                continue
            tree = self._parse_python_ast(context, file_context)
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                branch_count = sum(isinstance(child, BRANCH_NODE_TYPES) for child in ast.walk(node))
                if branch_count > self.max_branch_nodes:
                    issues.append(
                        Issue(
                            rule_id="structure.complex-function",
                            title="Function has high branch complexity",
                            description="Function contains many branch nodes and may be difficult to reason about.",
                            severity="medium",
                            path=file_context.path,
                            line=node.lineno,
                            confidence=0.9,
                            evidence=[f"function={node.name}", f"branch_nodes={branch_count}"],
                        )
                    )
        return issues

    def _detect_unused_imports(self, context: ReviewContext) -> list[Issue]:
        issues: list[Issue] = []
        for file_context in context.file_contexts:
            if file_context.language != "python":
                continue
            tree = self._parse_python_ast(context, file_context)
            imported_names: dict[str, int] = {}
            used_names: set[str] = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_names[alias.asname or alias.name.split(".")[-1]] = node.lineno
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported_names[alias.asname or alias.name] = node.lineno
                elif isinstance(node, ast.Name):
                    used_names.add(node.id)

            for imported_name, line_number in imported_names.items():
                if imported_name not in used_names:
                    issues.append(
                        Issue(
                            rule_id="structure.unused-import",
                            title="Unused import detected",
                            description="Imported symbol does not appear to be referenced in the file.",
                            severity="low",
                            path=file_context.path,
                            line=line_number,
                            confidence=0.75,
                            evidence=[imported_name],
                        )
                    )
        return issues

    def _detect_unused_symbols(self, context: ReviewContext) -> list[Issue]:
        issues: list[Issue] = []
        symbol_usage: dict[str, set[str]] = {}
        symbol_imports: dict[str, set[str]] = {}

        for file_context in context.file_contexts:
            if file_context.language != "python":
                continue
            tree = self._parse_python_ast(context, file_context)
            names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            symbol_usage[file_context.path] = names
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.add(alias.asname or alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.asname or alias.name.split(".")[-1])
            symbol_imports[file_context.path] = imports

        for file_context in context.file_contexts:
            if file_context.language != "python":
                continue
            local_names = symbol_usage.get(file_context.path, set())

            for function in file_context.functions:
                if function.name.startswith("test_") or function.name == "run":
                    continue
                if len(context.file_contexts) == 1 and function.name in local_names:
                    continue
                if not self._is_symbol_used_elsewhere(file_context.path, function.name, symbol_usage, symbol_imports):
                    issues.append(
                        Issue(
                            rule_id="structure.unused-function",
                            title="Function appears unused",
                            description="Function definition is not referenced in other parsed files and may be dead code.",
                            severity="low",
                            path=file_context.path,
                            line=function.line_start,
                            confidence=0.55,
                            evidence=[function.name, "heuristic=cross-file-name-reference"],
                        )
                    )

            for class_symbol in file_context.classes:
                if len(context.file_contexts) == 1 and class_symbol.name in local_names:
                    continue
                if not self._is_symbol_used_elsewhere(file_context.path, class_symbol.name, symbol_usage, symbol_imports):
                    issues.append(
                        Issue(
                            rule_id="structure.unused-class",
                            title="Class appears unused",
                            description="Class definition is not referenced in other parsed files and may be dead code.",
                            severity="low",
                            path=file_context.path,
                            line=class_symbol.line_start,
                            confidence=0.55,
                            evidence=[class_symbol.name, "heuristic=cross-file-name-reference"],
                        )
                    )

        return issues

    def _is_symbol_used_elsewhere(
        self,
        current_path: str,
        symbol_name: str,
        symbol_usage: dict[str, set[str]],
        symbol_imports: dict[str, set[str]],
    ) -> bool:
        for path, names in symbol_usage.items():
            if path == current_path:
                continue
            if symbol_name in names or symbol_name in symbol_imports.get(path, set()):
                return True
        return False
