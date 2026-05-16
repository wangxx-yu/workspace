from __future__ import annotations

import logging

from src.agents.base import BaseReviewAgent
from src.common.schemas import FailedFile, FileReviewContext, ProjectGraph, Report, ReportMetadata, ReviewContext
from src.common.settings import AppSettings
from src.context.manager import CodeReviewContextManager
from src.control.service import ReviewExecutionService
from src.input.dependency_extractor import DependencyExtractor
from src.input.parser import CodeParser
from src.input.repo_loader import RepoLoader
from src.input.scanner import RepositoryScanner


LOGGER = logging.getLogger(__name__)


class InputPipeline:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.repo_loader = RepoLoader(settings)
        self.scanner = RepositoryScanner(settings)
        self.parser = CodeParser()
        self.dependency_extractor = DependencyExtractor()

    def analyze(self, repo_ref: str, *, summary_only: bool = False) -> Report:
        loaded_repo = self.repo_loader.load(repo_ref)
        repo_path = loaded_repo.path
        try:
            BaseReviewAgent.set_cache_max_entries(self.settings.agent_cache_max_entries)
            BaseReviewAgent.clear_repo_cache(str(repo_path))
            BaseReviewAgent.reset_cache_metrics()
            context_manager = CodeReviewContextManager(self.settings, repo_path)
            scanned_files, skipped = self.scanner.scan(repo_path)

            parsed_files = []
            failed_files: list[FailedFile] = [
                FailedFile(path=path, reason="filtered_or_budget_exceeded", stage="scan") for path in skipped
            ]

            for scanned_file in scanned_files:
                try:
                    parsed_files.append(self.parser.parse(scanned_file))
                except Exception as exc:
                    LOGGER.warning(
                        "parse failed",
                        extra={"phase": "stage1", "file_path": scanned_file.relative_path},
                        exc_info=exc,
                    )
                    failed_files.append(
                        FailedFile(path=scanned_file.relative_path, reason=str(exc), stage="parse")
                    )

            project_graph = self.dependency_extractor.build_graph(parsed_files)
            review_context = context_manager.build(parsed_files, project_graph, summary_only=summary_only)
            review_context, issues, execution, recovery, feedback, summary = ReviewExecutionService(self.settings).execute(
                review_context,
                summary_only=summary_only,
            )
            metadata = ReportMetadata(
                repo_path=str(repo_path),
                total_files_scanned=len(scanned_files) + len(skipped),
                total_files_parsed=len(parsed_files),
                total_failed_files=len(failed_files),
                cache_content_hits=BaseReviewAgent.get_cache_metrics()["content_hits"],
                cache_content_misses=BaseReviewAgent.get_cache_metrics()["content_misses"],
                cache_ast_hits=BaseReviewAgent.get_cache_metrics()["ast_hits"],
                cache_ast_misses=BaseReviewAgent.get_cache_metrics()["ast_misses"],
                executed_agents=(execution.completed_order if execution is not None else self.settings.summary_task_order),
            )
            if summary is not None:
                summary = summary.model_copy(
                    update={
                        "metrics": {
                            "cache_content_hits": metadata.cache_content_hits,
                            "cache_content_misses": metadata.cache_content_misses,
                            "cache_ast_hits": metadata.cache_ast_hits,
                            "cache_ast_misses": metadata.cache_ast_misses,
                            "executed_agents": metadata.executed_agents,
                        }
                    }
                )
            report_parsed_files = [] if summary_only else parsed_files
            report_project_graph = project_graph if not summary_only else ProjectGraph(nodes=[], edges=[])
            report_review_context = None if summary_only else review_context
            history_context = self._compress_history_context(review_context) if summary_only else review_context
            context_manager.persist_history(history_context)
            return Report(
                parsed_files=report_parsed_files,
                project_graph=report_project_graph,
                failed_files=failed_files,
                issues=issues,
                metadata=metadata,
                review_context=report_review_context,
                execution=execution,
                recovery=recovery,
                feedback=feedback,
                summary=summary,
            )
        finally:
            loaded_repo.cleanup()

    def _compress_history_context(self, review_context: ReviewContext) -> ReviewContext:
        compressed_file_contexts = [
            FileReviewContext(
                path=item.path,
                language=item.language,
                content_hash=item.content_hash,
                size_bytes=item.size_bytes,
                suggestions=item.suggestions,
            )
            for item in review_context.file_contexts
        ]
        return review_context.model_copy(update={"file_contexts": compressed_file_contexts})
