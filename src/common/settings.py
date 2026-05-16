from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CODE_REVIEW_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    include_globs: list[str] = Field(default_factory=lambda: ["**/*.py", "**/*.js", "**/*.ts", "**/*.java"])
    exclude_globs: list[str] = Field(
        default_factory=lambda: [
            ".git/**",
            "node_modules/**",
            "__pycache__/**",
            ".venv/**",
            "venv/**",
            "dist/**",
            "build/**",
        ]
    )
    max_workers: int = 4
    max_files: int = 500
    max_file_bytes: int = 200_000
    max_total_bytes: int = 5_000_000
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    model_name: str = "mock-model"
    enable_llm: bool = False
    structure_summary_max_paths: int = 20
    dependency_edge_cap: int = 100
    key_files_cap: int = 10
    history_max_entries: int = 5000
    history_file_path: str = ".code-review-history.json"
    tokenizer_name: str = "simple-char-budget"
    structure_summary_cap: int = 4000
    key_files_token_cap: int = 4000
    dependency_token_cap: int = 4000
    per_file_issue_budget: int = 1000
    structure_max_function_lines: int = 40
    structure_max_branch_nodes: int = 8
    style_max_function_lines: int = 30
    style_max_parameters: int = 5
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_reset_seconds: int = 30
    allow_apply_with_git: bool = False
    review_changed_files_only: bool = True
    report_only_new_issues: bool = True
    self_verification_enabled: bool = True
    self_verification_max_attempts: int = 2
    test_command: str = "pytest"
    test_timeout_seconds: int = 20
    test_execution_enabled: bool = False
    agent_cache_max_entries: int = 2000
    git_clone_timeout_seconds: int = 60
    git_shallow_clone_depth: int = 1
    temp_repo_parent_dir: str = tempfile.gettempdir()
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    review_task_order: list[str] = Field(
        default_factory=lambda: ["structure", "security", "style", "performance", "test"]
    )
    review_task_dependencies: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "structure": [],
            "security": ["structure"],
            "style": ["structure"],
            "performance": ["structure"],
            "test": ["structure"],
        }
    )
    summary_task_order: list[str] = Field(default_factory=lambda: ["structure", "security", "test"])
    summary_task_dependencies: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "structure": [],
            "security": ["structure"],
            "test": ["structure"],
        }
    )
    run_mode: Literal["analyze_only", "propose_patch", "apply_with_git"] = "analyze_only"
    output_format: Literal["json", "markdown"] = "json"
    config_path: Path | None = None
