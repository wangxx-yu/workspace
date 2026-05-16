from __future__ import annotations

import ast
from collections import OrderedDict
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from src.common.schemas import AgentReport, FileReviewContext, ReviewContext
from src.common.settings import AppSettings


class BaseReviewAgent(ABC):
    agent_name: str
    _content_cache: ClassVar[OrderedDict[tuple[str, str, str], str]] = OrderedDict()
    _ast_cache: ClassVar[OrderedDict[tuple[str, str, str], ast.AST]] = OrderedDict()
    _cache_max_entries: ClassVar[int] = AppSettings().agent_cache_max_entries
    _content_hits: ClassVar[int] = 0
    _content_misses: ClassVar[int] = 0
    _ast_hits: ClassVar[int] = 0
    _ast_misses: ClassVar[int] = 0

    @abstractmethod
    def run(self, context: ReviewContext) -> AgentReport:
        raise NotImplementedError

    def _read_file_content(self, context: ReviewContext, file_context: FileReviewContext) -> str:
        cache_key = (context.repo_path, file_context.path, file_context.content_hash)
        cached = self._content_cache.get(cache_key)
        if cached is not None:
            BaseReviewAgent._content_hits += 1
            self._content_cache.move_to_end(cache_key)
            return cached
        BaseReviewAgent._content_misses += 1
        content = (Path(context.repo_path) / file_context.path).read_text(encoding="utf-8")
        self._content_cache[cache_key] = content
        self._content_cache.move_to_end(cache_key)
        self._enforce_cache_bounds()
        return content

    def _parse_python_ast(self, context: ReviewContext, file_context: FileReviewContext) -> ast.AST:
        cache_key = (context.repo_path, file_context.path, file_context.content_hash)
        cached = self._ast_cache.get(cache_key)
        if cached is not None:
            BaseReviewAgent._ast_hits += 1
            self._ast_cache.move_to_end(cache_key)
            return cached
        BaseReviewAgent._ast_misses += 1
        tree = ast.parse(self._read_file_content(context, file_context), filename=file_context.path)
        self._ast_cache[cache_key] = tree
        self._ast_cache.move_to_end(cache_key)
        self._enforce_cache_bounds()
        return tree

    @classmethod
    def warm_file_cache(cls, repo_path: str, file_path: str, content_hash: str, content: str) -> None:
        cls._content_cache[(repo_path, file_path, content_hash)] = content
        cls._content_cache.move_to_end((repo_path, file_path, content_hash))
        cls._enforce_cache_bounds()

    @classmethod
    def warm_ast_cache(cls, repo_path: str, file_path: str, content_hash: str, tree: ast.AST) -> None:
        cls._ast_cache[(repo_path, file_path, content_hash)] = tree
        cls._ast_cache.move_to_end((repo_path, file_path, content_hash))
        cls._enforce_cache_bounds()

    @classmethod
    def clear_repo_cache(cls, repo_path: str) -> None:
        cls._content_cache = OrderedDict(
            (key, value) for key, value in cls._content_cache.items() if key[0] != repo_path
        )
        cls._ast_cache = OrderedDict(
            (key, value) for key, value in cls._ast_cache.items() if key[0] != repo_path
        )

    @classmethod
    def set_cache_max_entries(cls, max_entries: int) -> None:
        cls._cache_max_entries = max_entries
        cls._enforce_cache_bounds()

    @classmethod
    def reset_cache_metrics(cls) -> None:
        cls._content_hits = 0
        cls._content_misses = 0
        cls._ast_hits = 0
        cls._ast_misses = 0

    @classmethod
    def get_cache_metrics(cls) -> dict[str, int]:
        return {
            "content_hits": cls._content_hits,
            "content_misses": cls._content_misses,
            "ast_hits": cls._ast_hits,
            "ast_misses": cls._ast_misses,
        }

    @classmethod
    def _enforce_cache_bounds(cls) -> None:
        while len(cls._content_cache) > cls._cache_max_entries:
            cls._content_cache.popitem(last=False)
        while len(cls._ast_cache) > cls._cache_max_entries:
            cls._ast_cache.popitem(last=False)
