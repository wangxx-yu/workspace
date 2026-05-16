from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class SymbolReference(BaseModel):
    name: str
    kind: Literal["function", "class", "import", "module"]
    line_start: int
    line_end: int
    parameter_count: int | None = None


class ParsedFile(BaseModel):
    path: str
    language: str
    parse_mode: Literal["ast", "text"]
    size_bytes: int
    content_hash: str
    imports: list[str] = Field(default_factory=list)
    functions: list[SymbolReference] = Field(default_factory=list)
    classes: list[SymbolReference] = Field(default_factory=list)
    parse_errors: list[str] = Field(default_factory=list)


class DependencyEdge(BaseModel):
    source: str
    target: str
    edge_type: Literal["import"] = "import"
    resolution_confidence: float = Field(ge=0.0, le=1.0)
    resolved: bool = False


class ProjectGraph(BaseModel):
    nodes: list[str]
    edges: list[DependencyEdge]


class FailedFile(BaseModel):
    path: str
    reason: str
    stage: Literal["scan", "parse", "dependency"]


class Issue(BaseModel):
    rule_id: str
    title: str
    description: str
    severity: Literal["critical", "high", "medium", "low"]
    path: str
    line: int | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    evidence: list[str] = Field(default_factory=list)


class ReportMetadata(BaseModel):
    repo_path: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_files_scanned: int
    total_files_parsed: int
    total_failed_files: int
    cache_content_hits: int = 0
    cache_content_misses: int = 0
    cache_ast_hits: int = 0
    cache_ast_misses: int = 0
    executed_agents: list[str] = Field(default_factory=list)


class FileReviewContext(BaseModel):
    path: str
    language: str
    content_hash: str
    size_bytes: int
    imports: list[str] = Field(default_factory=list)
    functions: list[SymbolReference] = Field(default_factory=list)
    classes: list[SymbolReference] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class StructureSummary(BaseModel):
    total_files: int
    language_distribution: dict[str, int]
    highlighted_paths: list[str] = Field(default_factory=list)


class KeyFileReference(BaseModel):
    path: str
    reason: str
    score: int


class HistoricalFingerprint(BaseModel):
    path: str
    content_hash: str
    issue_fingerprints: list[str] = Field(default_factory=list)


class IncrementalReviewState(BaseModel):
    changed_files: list[str] = Field(default_factory=list)
    unchanged_files: list[str] = Field(default_factory=list)
    new_or_changed_paths: list[str] = Field(default_factory=list)
    historical_fingerprints: list[HistoricalFingerprint] = Field(default_factory=list)


class ContextBudget(BaseModel):
    tokenizer_name: str
    estimated_tokens: int
    structure_summary_cap: int
    key_files_token_cap: int
    dependency_token_cap: int
    per_file_issue_budget: int
    within_budget: bool
    truncation_reason: str | None = None


class ReviewContext(BaseModel):
    repo_path: str
    file_contexts: list[FileReviewContext]
    target_file_paths: list[str] = Field(default_factory=list)
    structure_summary: StructureSummary
    key_files: list[KeyFileReference]
    dependency_focus_paths: list[str]
    incremental_state: IncrementalReviewState
    budget: ContextBudget


class AgentReport(BaseModel):
    agent_name: str
    issues: list[Issue] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    severity: Literal["critical", "high", "medium", "low", "info"] = "info"


class TaskResult(BaseModel):
    task_id: str
    agent_name: str
    status: Literal["pending", "running", "completed", "failed"]
    depends_on: list[str] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0
    recovery_action: str | None = None
    degraded: bool = False


class ReviewExecution(BaseModel):
    ready_order: list[str] = Field(default_factory=list)
    completed_order: list[str] = Field(default_factory=list)
    failed_tasks: list[str] = Field(default_factory=list)
    task_results: list[TaskResult] = Field(default_factory=list)
    progress: float = 0.0


class CircuitBreakerState(BaseModel):
    agent_name: str
    status: Literal["closed", "open", "half_open"] = "closed"
    consecutive_failures: int = 0
    opened_at_epoch: float | None = None


class RecoveryEvent(BaseModel):
    scope: Literal["task", "file", "run_mode"]
    target: str
    action: str
    reason: str


class RecoverySummary(BaseModel):
    mode_requested: Literal["analyze_only", "propose_patch", "apply_with_git"]
    mode_effective: Literal["analyze_only", "propose_patch", "apply_with_git"]
    circuit_breakers: list[CircuitBreakerState] = Field(default_factory=list)
    events: list[RecoveryEvent] = Field(default_factory=list)


class VerificationAttempt(BaseModel):
    attempt: int
    action: str
    result: Literal["passed", "failed", "skipped"]
    detail: str


class FeedbackSummary(BaseModel):
    target_file_paths: list[str] = Field(default_factory=list)
    issue_count_by_file: dict[str, int] = Field(default_factory=dict)
    agent_issue_counts: dict[str, int] = Field(default_factory=dict)
    structure_findings: list[str] = Field(default_factory=list)
    test_summary: dict[str, str] = Field(default_factory=dict)
    verification_attempts: list[VerificationAttempt] = Field(default_factory=list)


class ReportSummary(BaseModel):
    repo_path: str
    total_issues: int
    total_files_parsed: int
    target_files: list[str] = Field(default_factory=list)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    agent_counts: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, int | list[str]] = Field(default_factory=dict)


class Report(BaseModel):
    parsed_files: list[ParsedFile]
    project_graph: ProjectGraph
    failed_files: list[FailedFile]
    issues: list[Issue] = Field(default_factory=list)
    metadata: ReportMetadata
    review_context: ReviewContext | None = None
    execution: ReviewExecution | None = None
    recovery: RecoverySummary | None = None
    feedback: FeedbackSummary | None = None
    summary: ReportSummary | None = None
