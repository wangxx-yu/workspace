from __future__ import annotations

import fnmatch
from pathlib import Path

from src.common.settings import AppSettings
from src.input.models import ScannedFile


LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
}


class RepositoryScanner:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def scan(self, repo_path: Path) -> tuple[list[ScannedFile], list[str]]:
        scanned: list[ScannedFile] = []
        skipped: list[str] = []
        total_bytes = 0

        for path in sorted(repo_path.rglob("*")):
            if not path.is_file():
                continue

            relative_path = path.relative_to(repo_path).as_posix()
            if relative_path == self.settings.history_file_path:
                continue
            if self._is_excluded(relative_path):
                skipped.append(relative_path)
                continue

            if not self._is_included(relative_path):
                skipped.append(relative_path)
                continue

            size_bytes = path.stat().st_size
            if size_bytes > self.settings.max_file_bytes:
                skipped.append(relative_path)
                continue

            if len(scanned) >= self.settings.max_files:
                skipped.append(relative_path)
                continue

            if total_bytes + size_bytes > self.settings.max_total_bytes:
                skipped.append(relative_path)
                continue

            total_bytes += size_bytes
            scanned.append(
                ScannedFile(
                    path=path,
                    relative_path=relative_path,
                    size_bytes=size_bytes,
                    language=LANGUAGE_BY_SUFFIX.get(path.suffix, "text"),
                )
            )

        return scanned, skipped

    def _is_included(self, relative_path: str) -> bool:
        return any(self._matches(relative_path, pattern) for pattern in self.settings.include_globs)

    def _is_excluded(self, relative_path: str) -> bool:
        return any(self._matches(relative_path, pattern) for pattern in self.settings.exclude_globs)

    def _matches(self, relative_path: str, pattern: str) -> bool:
        if fnmatch.fnmatch(relative_path, pattern):
            return True
        if pattern.startswith("**/"):
            return fnmatch.fnmatch(relative_path, pattern[3:])
        return False
