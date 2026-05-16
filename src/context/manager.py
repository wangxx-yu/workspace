from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.common.schemas import (
    ContextBudget,
    FileReviewContext,
    HistoricalFingerprint,
    IncrementalReviewState,
    KeyFileReference,
    ParsedFile,
    ProjectGraph,
    ReviewContext,
    StructureSummary,
)
from src.common.settings import AppSettings
from src.context.history import HistoryStore


ENTRYPOINT_NAMES = {"main.py", "app.py", "manage.py", "index.ts", "index.js"}
CONFIG_NAMES = {"pyproject.toml", "package.json", "tsconfig.json", "requirements.txt"}


class CodeReviewContextManager:
    def __init__(self, settings: AppSettings, repo_path: Path) -> None:
        self.settings = settings
        self.repo_path = repo_path
        self.history_store = HistoryStore(repo_path / settings.history_file_path, settings.history_max_entries)

    def build(
        self,
        parsed_files: list[ParsedFile],
        project_graph: ProjectGraph,
        *,
        summary_only: bool = False,
    ) -> ReviewContext:
        self._historical_entries = self.history_store.load()
        file_contexts = self._create_file_contexts(parsed_files, project_graph)
        structure_summary = self._generate_structure_summary(parsed_files)
        key_files = self._identify_key_files(parsed_files, project_graph)
        dependency_focus_paths = self._extract_dependencies(project_graph, key_files)
        incremental_state = self._build_incremental_state(parsed_files)
        target_file_paths = self._select_target_file_paths(parsed_files, incremental_state)
        budget = self._estimate_budget(structure_summary, key_files, dependency_focus_paths, len(file_contexts))
        if summary_only:
            key_files = []
            dependency_focus_paths = []
            structure_summary = structure_summary.model_copy(update={"highlighted_paths": []})
        return ReviewContext(
            repo_path=str(self.repo_path),
            file_contexts=file_contexts,
            target_file_paths=target_file_paths,
            structure_summary=structure_summary,
            key_files=key_files,
            dependency_focus_paths=dependency_focus_paths,
            incremental_state=incremental_state,
            budget=budget,
        )

    def persist_history(self, review_context: ReviewContext) -> None:
        entries = {
            item.path: HistoricalFingerprint(
                path=item.path,
                content_hash=item.content_hash,
                issue_fingerprints=[self._fingerprint_issue(path=item.path, description=text) for text in item.suggestions],
            )
            for item in review_context.file_contexts
        }
        self.history_store.save(entries)

    def _create_file_contexts(
        self, parsed_files: list[ParsedFile], project_graph: ProjectGraph
    ) -> list[FileReviewContext]:
        dependencies_by_source: dict[str, list[str]] = {}
        for edge in project_graph.edges:
            dependencies_by_source.setdefault(edge.source, []).append(edge.target)

        return [
            FileReviewContext(
                path=item.path,
                language=item.language,
                content_hash=item.content_hash,
                size_bytes=item.size_bytes,
                imports=item.imports,
                functions=item.functions,
                classes=item.classes,
                dependencies=sorted(dependencies_by_source.get(item.path, [])),
            )
            for item in parsed_files
        ]

    def _generate_structure_summary(self, parsed_files: list[ParsedFile]) -> StructureSummary:
        distribution = Counter(item.language for item in parsed_files)
        highlighted_paths = [item.path for item in parsed_files[: self.settings.structure_summary_max_paths]]
        return StructureSummary(
            total_files=len(parsed_files),
            language_distribution=dict(sorted(distribution.items())),
            highlighted_paths=highlighted_paths,
        )

    def _identify_key_files(
        self, parsed_files: list[ParsedFile], project_graph: ProjectGraph
    ) -> list[KeyFileReference]:
        degree_counter: Counter[str] = Counter()
        for edge in project_graph.edges:
            degree_counter[edge.source] += 1
            if edge.resolved:
                degree_counter[edge.target] += 1

        scored: list[KeyFileReference] = []
        for parsed_file in parsed_files:
            score = degree_counter[parsed_file.path]
            reasons: list[str] = []

            name = Path(parsed_file.path).name
            if name in ENTRYPOINT_NAMES:
                score += 5
                reasons.append("entrypoint")
            if name in CONFIG_NAMES:
                score += 4
                reasons.append("config")
            if parsed_file.path.count("/") == 0:
                score += 1
                reasons.append("top-level")
            if degree_counter[parsed_file.path] > 0:
                reasons.append("high-degree")

            if score > 0:
                scored.append(
                    KeyFileReference(
                        path=parsed_file.path,
                        reason=",".join(reasons) or "scored",
                        score=score,
                    )
                )

        scored.sort(key=lambda item: (-item.score, item.path))
        return scored[: self.settings.key_files_cap]

    def _extract_dependencies(
        self, project_graph: ProjectGraph, key_files: list[KeyFileReference]
    ) -> list[str]:
        key_file_paths = {item.path for item in key_files}
        focus_paths: list[str] = []

        for edge in project_graph.edges[: self.settings.dependency_edge_cap]:
            if edge.source in key_file_paths or edge.target in key_file_paths:
                if edge.source not in focus_paths:
                    focus_paths.append(edge.source)
                if edge.target not in focus_paths:
                    focus_paths.append(edge.target)

        return focus_paths[: self.settings.dependency_edge_cap]

    def _build_incremental_state(self, parsed_files: list[ParsedFile]) -> IncrementalReviewState:
        historical_entries = getattr(self, "_historical_entries", self.history_store.load())
        changed_files: list[str] = []
        unchanged_files: list[str] = []
        new_or_changed_paths: list[str] = []

        for parsed_file in parsed_files:
            historical = historical_entries.get(parsed_file.path)
            if historical is None or historical.content_hash != parsed_file.content_hash:
                changed_files.append(parsed_file.path)
                new_or_changed_paths.append(parsed_file.path)
            else:
                unchanged_files.append(parsed_file.path)

        return IncrementalReviewState(
            changed_files=changed_files,
            unchanged_files=unchanged_files,
            new_or_changed_paths=new_or_changed_paths,
            historical_fingerprints=list(historical_entries.values()),
        )

    def _select_target_file_paths(
        self,
        parsed_files: list[ParsedFile],
        incremental_state: IncrementalReviewState,
    ) -> list[str]:
        if self.settings.review_changed_files_only and incremental_state.new_or_changed_paths:
            return list(incremental_state.new_or_changed_paths)
        return [item.path for item in parsed_files]

    def _estimate_budget(
        self,
        structure_summary: StructureSummary,
        key_files: list[KeyFileReference],
        dependency_focus_paths: list[str],
        file_count: int,
    ) -> ContextBudget:
        estimated_tokens = (
            sum(len(path) for path in structure_summary.highlighted_paths)
            + sum(len(item.path) + len(item.reason) for item in key_files)
            + sum(len(path) for path in dependency_focus_paths)
            + file_count * 40
        )
        budget_limit = (
            self.settings.structure_summary_cap
            + self.settings.key_files_token_cap
            + self.settings.dependency_token_cap
            + file_count * self.settings.per_file_issue_budget
        )
        within_budget = estimated_tokens <= budget_limit
        truncation_reason = None if within_budget else "estimated_tokens_exceeded_budget"
        return ContextBudget(
            tokenizer_name=self.settings.tokenizer_name,
            estimated_tokens=estimated_tokens,
            structure_summary_cap=self.settings.structure_summary_cap,
            key_files_token_cap=self.settings.key_files_token_cap,
            dependency_token_cap=self.settings.dependency_token_cap,
            per_file_issue_budget=self.settings.per_file_issue_budget,
            within_budget=within_budget,
            truncation_reason=truncation_reason,
        )

    def _fingerprint_issue(self, path: str, description: str) -> str:
        return f"{path}:{description.strip().lower()}"
