from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from src.agents.base import BaseReviewAgent
from src.common.schemas import ParsedFile, SymbolReference
from src.input.models import ScannedFile


class CodeParser:
    def parse(self, scanned_file: ScannedFile) -> ParsedFile:
        content = scanned_file.path.read_text(encoding="utf-8")
        content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()
        repo_path = str(scanned_file.path.parent if scanned_file.path.name == scanned_file.relative_path else self._resolve_repo_root(scanned_file))
        BaseReviewAgent.warm_file_cache(repo_path, scanned_file.relative_path, content_hash, content)

        if scanned_file.language == "python":
            return self._parse_python(scanned_file, content, content_hash, repo_path)

        return ParsedFile(
            path=scanned_file.relative_path,
            language=scanned_file.language,
            parse_mode="text",
            size_bytes=scanned_file.size_bytes,
            content_hash=content_hash,
        )

    def _parse_python(self, scanned_file: ScannedFile, content: str, content_hash: str, repo_path: str) -> ParsedFile:
        tree = ast.parse(content, filename=scanned_file.relative_path)
        BaseReviewAgent.warm_ast_cache(repo_path, scanned_file.relative_path, content_hash, tree)
        imports: list[str] = []
        functions: list[SymbolReference] = []
        classes: list[SymbolReference] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
            elif isinstance(node, ast.FunctionDef):
                functions.append(
                    SymbolReference(
                        name=node.name,
                        kind="function",
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        parameter_count=len(node.args.args),
                    )
                )
            elif isinstance(node, ast.ClassDef):
                classes.append(
                    SymbolReference(
                        name=node.name,
                        kind="class",
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                    )
                )

        return ParsedFile(
            path=scanned_file.relative_path,
            language="python",
            parse_mode="ast",
            size_bytes=scanned_file.size_bytes,
            content_hash=content_hash,
            imports=sorted(set(imports)),
            functions=sorted(functions, key=lambda item: (item.line_start, item.name)),
            classes=sorted(classes, key=lambda item: (item.line_start, item.name)),
        )

    def _resolve_repo_root(self, scanned_file: ScannedFile) -> Path:
        relative_parts = Path(scanned_file.relative_path).parts
        path = scanned_file.path
        for _ in relative_parts:
            path = path.parent
        return path
