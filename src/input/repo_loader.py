from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from git import GitCommandError, Repo

from src.common.settings import AppSettings


@dataclass(slots=True)
class LoadedRepository:
    path: Path
    cleanup_path: Path | None = None

    def cleanup(self) -> None:
        if self.cleanup_path is not None and self.cleanup_path.exists():
            shutil.rmtree(self.cleanup_path)


@dataclass(slots=True)
class RepoCloneError(Exception):
    repo_ref: str
    category: str
    detail: str

    def __str__(self) -> str:
        return f"Git clone failed [{self.category}] for repository: {self.repo_ref}: {self.detail}"


class RepoLoader:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def load(self, repo_ref: str) -> LoadedRepository:
        repo_ref = self._normalize_repo_ref(repo_ref)
        if self._is_git_url(repo_ref):
            return self._clone_remote(repo_ref)
        return self._load_local(repo_ref)

    def _load_local(self, repo_ref: str) -> LoadedRepository:
        path = Path(repo_ref).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo_ref}")
        if not path.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {repo_ref}")
        return LoadedRepository(path=path)

    def _clone_remote(self, repo_ref: str) -> LoadedRepository:
        parent_dir = Path(self.settings.temp_repo_parent_dir)
        temp_dir = Path(
            tempfile.mkdtemp(prefix="code-review-agent-", dir=str(parent_dir))
        )
        clone_dir = temp_dir / "repo"
        try:
            completed = subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    str(self.settings.git_shallow_clone_depth),
                    repo_ref,
                    str(clone_dir),
                ],
                capture_output=True,
                text=True,
                timeout=self.settings.git_clone_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            shutil.rmtree(temp_dir)
            raise TimeoutError(f"Git clone timed out for repository: {repo_ref}") from exc

        if completed.returncode != 0:
            shutil.rmtree(temp_dir)
            stderr = completed.stderr.strip() or "git clone failed"
            raise RepoCloneError(repo_ref=repo_ref, category=self._classify_clone_error(stderr), detail=stderr)

        return LoadedRepository(path=clone_dir, cleanup_path=temp_dir)

    def _is_git_url(self, repo_ref: str) -> bool:
        return repo_ref.startswith(("https://", "http://", "git@", "ssh://", "file://"))

    def _normalize_repo_ref(self, repo_ref: str) -> str:
        if repo_ref.startswith(("https://github.com/", "http://github.com/")) and not repo_ref.endswith(".git"):
            return f"{repo_ref}.git"
        return repo_ref

    def _classify_clone_error(self, stderr: str) -> str:
        lowered = stderr.lower()
        if "repository not found" in lowered or "not found" in lowered:
            return "repository_not_found"
        if "permission denied" in lowered or "access denied" in lowered or "authentication failed" in lowered:
            return "permission_denied"
        if "could not resolve host" in lowered or "failed to connect" in lowered or "network is unreachable" in lowered:
            return "network_error"
        if "remote branch" in lowered or "reference is not a tree" in lowered or "couldn't find remote ref" in lowered:
            return "invalid_reference"
        return "unknown"
