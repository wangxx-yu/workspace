from __future__ import annotations

from typing import Literal

from fastapi import HTTPException
from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.common.schemas import Report, ReportSummary
from src.common.settings import AppSettings
from src.input.repo_loader import RepoCloneError
from src.input.service import InputPipeline
from src.output.formatter import ReportFormatter
from src.report_processing import ReportQueryOptions, build_filtered_summary, filter_report, trim_report


class QueryRequestBase(BaseModel):
    repo_ref: str = Field(description="本地仓库路径、Git URL 或 GitHub HTTPS URL")
    review_changed_files_only: bool | None = Field(default=None, description="是否仅审查增量变更文件")
    test_execution_enabled: bool | None = Field(default=None, description="是否执行测试命令")
    test_command: str | None = Field(default=None, description="测试命令，例如 pytest")
    test_timeout_seconds: int | None = Field(default=None, description="测试命令超时时间，单位秒")
    severity_filter: list[str] | None = Field(default=None, description="按严重级过滤，如 low/high")
    agent_filter: list[str] | None = Field(default=None, description="按 agent 名称过滤，如 test/security")
    path_filter: list[str] | None = Field(default=None, description="按文件路径过滤")
    sort_by: Literal["severity", "path"] | None = Field(default=None, description="结果排序方式")
    offset: int | None = Field(default=None, ge=0, description="结果起始偏移")
    limit: int | None = Field(default=None, ge=1, description="结果数量上限")


class AnalyzeRequest(QueryRequestBase):
    output_format: Literal["json", "markdown", "sarif"] | None = Field(default=None, description="格式化输出格式")
    include_parsed_files: bool = Field(default=True, description="是否包含 parsed_files")
    include_project_graph: bool = Field(default=True, description="是否包含 project_graph")
    include_review_context: bool = Field(default=True, description="是否包含 review_context")
    include_execution: bool = Field(default=True, description="是否包含 execution")
    include_feedback: bool = Field(default=True, description="是否包含 feedback")


class AnalyzeSummaryRequest(QueryRequestBase):
    pass


class ErrorBody(BaseModel):
    code: str = Field(description="稳定错误码")
    message: str = Field(description="错误描述")
    details: object | None = Field(default=None, description="结构化错误细节")


class ErrorResponse(BaseModel):
    error: ErrorBody


def _override_settings(base: AppSettings, request: QueryRequestBase) -> AppSettings:
    updates = {}
    for field_name in (
        "review_changed_files_only",
        "test_execution_enabled",
        "test_command",
        "test_timeout_seconds",
    ):
        value = getattr(request, field_name)
        if value is not None:
            updates[field_name] = value
    return base.model_copy(update=updates)


def _to_query_options(request: QueryRequestBase) -> ReportQueryOptions:
    return ReportQueryOptions(
        severity_filter=request.severity_filter,
        agent_filter=request.agent_filter,
        path_filter=request.path_filter,
        sort_by=request.sort_by,
        offset=request.offset,
        limit=request.limit,
        include_parsed_files=getattr(request, "include_parsed_files", True),
        include_project_graph=getattr(request, "include_project_graph", True),
        include_review_context=getattr(request, "include_review_context", True),
        include_execution=getattr(request, "include_execution", True),
        include_feedback=getattr(request, "include_feedback", True),
    )


def _error_response(status_code: int, code: str, message: str, details: object | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=ErrorBody(code=code, message=message, details=details)).model_dump(),
    )


def _analyze_report(settings: AppSettings, request: AnalyzeRequest) -> Report:
    try:
        report = InputPipeline(settings).analyze(request.repo_ref)
    except RepoCloneError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "repo_clone_failed",
                "message": str(exc),
                "details": {"category": exc.category, "repo_ref": exc.repo_ref},
            },
        ) from exc
    options = _to_query_options(request)
    report = filter_report(report, options)
    return trim_report(report, options)


def create_app(settings: AppSettings | None = None) -> FastAPI:
    app = FastAPI(title="Code Review Agent API", version="0.1.0")
    app_settings = settings or AppSettings()

    error_examples = {
        400: {
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "repo_clone_failed",
                            "message": "Git clone failed [repository_not_found] for repository: https://github.com/example/missing.git: fatal: repository not found",
                            "details": {
                                "category": "repository_not_found",
                                "repo_ref": "https://github.com/example/missing.git",
                            },
                        }
                    }
                }
            },
        },
        422: {
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "validation_error",
                            "message": "request validation failed",
                            "details": [
                                {
                                    "loc": ["body", "limit"],
                                    "msg": "Input should be greater than or equal to 1",
                                    "type": "greater_than_equal",
                                }
                            ],
                        }
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "internal_error",
                            "message": "unexpected server error",
                            "details": None,
                        }
                    }
                }
            },
        },
    }

    @app.exception_handler(HTTPException)
    def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and {"code", "message"}.issubset(detail):
            return _error_response(
                exc.status_code,
                detail["code"],
                detail["message"],
                detail.get("details"),
            )
        return _error_response(exc.status_code, "http_error", str(detail), None)

    @app.exception_handler(RequestValidationError)
    def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(422, "validation_error", "request validation failed", exc.errors())

    @app.exception_handler(Exception)
    def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(500, "internal_error", str(exc), None)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/analyze",
        response_model=Report,
        responses=error_examples,
        summary="执行完整分析",
        description="返回完整结构化报告，支持过滤、排序、分页和大字段裁剪。",
    )
    def analyze(request: AnalyzeRequest) -> Report:
        effective_settings = _override_settings(app_settings, request)
        return _analyze_report(effective_settings, request)

    @app.post(
        "/analyze-formatted",
        responses=error_examples,
        summary="执行格式化分析",
        description="返回 JSON、Markdown 或 SARIF 字符串内容。",
    )
    def analyze_formatted(request: AnalyzeRequest) -> dict[str, str]:
        effective_settings = _override_settings(app_settings, request)
        report = _analyze_report(effective_settings, request)
        formatter = ReportFormatter()
        output_format = request.output_format or "json"
        if output_format == "markdown":
            return {"format": output_format, "content": formatter.to_markdown(report)}
        if output_format == "sarif":
            return {"format": output_format, "content": formatter.to_sarif(report)}
        return {"format": "json", "content": formatter.to_json(report)}

    @app.post(
        "/analyze-summary",
        response_model=ReportSummary,
        responses=error_examples,
        summary="执行轻量摘要分析",
        description="返回 issue 数量、严重级分布、agent 分布和目标文件列表。",
    )
    def analyze_summary(request: AnalyzeSummaryRequest) -> ReportSummary:
        effective_settings = _override_settings(app_settings, request)
        try:
            report = InputPipeline(effective_settings).analyze(request.repo_ref, summary_only=True)
        except RepoCloneError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "repo_clone_failed",
                    "message": str(exc),
                    "details": {"category": exc.category, "repo_ref": exc.repo_ref},
                },
            ) from exc
        return build_filtered_summary(report, effective_settings, _to_query_options(request))

    return app
