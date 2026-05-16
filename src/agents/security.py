from __future__ import annotations

import ast
import re

from src.agents.base import BaseReviewAgent
from src.common.schemas import AgentReport, Issue, ReviewContext


SECRET_PATTERN = re.compile(
    r"(?i)(password|secret|token|api_key)\s*=\s*['\"][^'\"]+['\"]"
)
SHELL_PATTERN = re.compile(r"(os\.system\(|subprocess\.(run|Popen)\([^\n]*shell\s*=\s*True)")
EVAL_PATTERN = re.compile(r"\b(eval|exec)\s*\(")


class SecurityAgent(BaseReviewAgent):
    agent_name = "security"

    def run(self, context: ReviewContext) -> AgentReport:
        issues: list[Issue] = []

        for file_context in context.file_contexts:
            if file_context.language != "python":
                continue

            content = self._read_file_content(context, file_context)
            issues.extend(self._find_ast_issues(file_context.path, self._parse_python_ast(context, file_context)))
            issues.extend(
                self._find_pattern_issues(
                    file_context.path,
                    content,
                    SECRET_PATTERN,
                    "security.hardcoded-secret",
                    "Hardcoded secret detected",
                    "Potential credential or token is embedded in source code.",
                    "high",
                )
            )

        return AgentReport(
            agent_name=self.agent_name,
            issues=issues,
            evidence=[f"changed_files={len(context.incremental_state.changed_files)}"],
            severity="info" if not issues else "high",
        )

    def _find_ast_issues(self, path: str, tree: ast.AST) -> list[Issue]:
        issues: list[Issue] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                issues.extend(self._detect_shell_execution(path, node))
                issues.extend(self._detect_dynamic_execution(path, node))
                issues.extend(self._detect_pickle_loads(path, node))
                issues.extend(self._detect_yaml_load(path, node))
                issues.extend(self._detect_mktemp(path, node))
                issues.extend(self._detect_weak_random_usage(path, node))
            elif isinstance(node, ast.BinOp):
                issues.extend(self._detect_sql_string_concat(path, node))

        return issues

    def _detect_shell_execution(self, path: str, node: ast.Call) -> list[Issue]:
        func_name = self._call_name(node.func)
        if func_name not in {"os.system", "subprocess.run", "subprocess.Popen"}:
            return []

        has_shell_true = any(
            keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
            for keyword in node.keywords
        )
        if func_name == "os.system" or has_shell_true:
            return [
                Issue(
                    rule_id="security.shell-true",
                    title="Shell execution detected",
                    description="Shell execution can lead to command injection when arguments are influenced by user input.",
                    severity="high",
                    path=path,
                    line=getattr(node, "lineno", None),
                    confidence=0.95,
                    evidence=[func_name],
                )
            ]
        return []

    def _detect_dynamic_execution(self, path: str, node: ast.Call) -> list[Issue]:
        func_name = self._call_name(node.func)
        if func_name in {"eval", "exec"}:
            return [
                Issue(
                    rule_id="security.dynamic-execution",
                    title="Dynamic execution detected",
                    description="Dynamic execution primitives increase remote code execution risk.",
                    severity="medium",
                    path=path,
                    line=getattr(node, "lineno", None),
                    confidence=0.95,
                    evidence=[func_name],
                )
            ]
        return []

    def _detect_pickle_loads(self, path: str, node: ast.Call) -> list[Issue]:
        func_name = self._call_name(node.func)
        if func_name in {"pickle.load", "pickle.loads"}:
            return [
                Issue(
                    rule_id="security.insecure-deserialization",
                    title="Insecure deserialization detected",
                    description="Pickle deserialization can execute arbitrary code when input is untrusted.",
                    severity="high",
                    path=path,
                    line=getattr(node, "lineno", None),
                    confidence=0.95,
                    evidence=[func_name],
                )
            ]
        return []

    def _detect_yaml_load(self, path: str, node: ast.Call) -> list[Issue]:
        func_name = self._call_name(node.func)
        if func_name != "yaml.load":
            return []

        has_safe_loader = any(
            keyword.arg == "Loader"
            and self._call_name(keyword.value) in {"yaml.SafeLoader", "SafeLoader"}
            for keyword in node.keywords
        )
        if not has_safe_loader:
            return [
                Issue(
                    rule_id="security.unsafe-yaml-load",
                    title="Unsafe yaml.load detected",
                    description="yaml.load without SafeLoader can deserialize unsafe objects.",
                    severity="high",
                    path=path,
                    line=getattr(node, "lineno", None),
                    confidence=0.9,
                    evidence=[func_name],
                )
            ]
        return []

    def _detect_mktemp(self, path: str, node: ast.Call) -> list[Issue]:
        func_name = self._call_name(node.func)
        if func_name == "tempfile.mktemp":
            return [
                Issue(
                    rule_id="security.tempfile-mktemp",
                    title="Insecure tempfile.mktemp usage",
                    description="tempfile.mktemp can introduce race conditions and insecure temp file creation.",
                    severity="medium",
                    path=path,
                    line=getattr(node, "lineno", None),
                    confidence=0.95,
                    evidence=[func_name],
                )
            ]
        return []

    def _detect_weak_random_usage(self, path: str, node: ast.Call) -> list[Issue]:
        func_name = self._call_name(node.func)
        if func_name in {"random.random", "random.randint", "random.choice", "random.randrange"}:
            return [
                Issue(
                    rule_id="security.weak-random",
                    title="Weak random source detected",
                    description="The random module is unsuitable for security-sensitive token or secret generation.",
                    severity="low",
                    path=path,
                    line=getattr(node, "lineno", None),
                    confidence=0.7,
                    evidence=[func_name],
                )
            ]
        return []

    def _detect_sql_string_concat(self, path: str, node: ast.BinOp) -> list[Issue]:
        if not isinstance(node.op, ast.Add):
            return []
        if not self._contains_sql_literal(node):
            return []
        return [
            Issue(
                rule_id="security.sql-string-concat",
                title="SQL string concatenation detected",
                description="SQL query construction via string concatenation may lead to injection risks.",
                severity="high",
                path=path,
                line=getattr(node, "lineno", None),
                confidence=0.8,
                evidence=["sql_concat"],
            )
        ]

    def _contains_sql_literal(self, node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                upper_text = child.value.upper()
                if any(keyword in upper_text for keyword in {"SELECT ", "INSERT ", "UPDATE ", "DELETE "}):
                    return True
        return False

    def _call_name(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base_name = self._call_name(node.value)
            if base_name is None:
                return node.attr
            return f"{base_name}.{node.attr}"
        return None

    def _find_pattern_issues(
        self,
        path: str,
        content: str,
        pattern: re.Pattern[str],
        rule_id: str,
        title: str,
        description: str,
        severity: str,
    ) -> list[Issue]:
        issues: list[Issue] = []
        for line_number, line in enumerate(content.splitlines(), start=1):
            match = pattern.search(line)
            if match:
                issues.append(
                    Issue(
                        rule_id=rule_id,
                        title=title,
                        description=description,
                        severity=severity,
                        path=path,
                        line=line_number,
                        confidence=0.9,
                        evidence=[line.strip()],
                    )
                )
        return issues
