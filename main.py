from __future__ import annotations

import argparse
import json
import logging
import sys

import uvicorn

from src.common.logging import configure_logging
from src.common.settings import AppSettings
from src.api import AnalyzeRequest, create_app
from src.input.service import InputPipeline
from src.output.formatter import ReportFormatter
from src.report_processing import ReportQueryOptions, build_filtered_summary, filter_report, trim_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Code Review Agent CLI")
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a repository path")
    analyze_parser.add_argument("--repo", required=True, help="Local repository path")
    analyze_parser.add_argument("--format", choices=["json", "markdown", "sarif"], default=None)
    analyze_parser.add_argument("--review-changed-files-only", choices=["true", "false"], default=None)
    analyze_parser.add_argument("--test-execution-enabled", choices=["true", "false"], default=None)
    analyze_parser.add_argument("--test-command", default=None)
    analyze_parser.add_argument("--test-timeout-seconds", type=int, default=None)
    analyze_parser.add_argument("--severity-filter", action="append", default=None)
    analyze_parser.add_argument("--agent-filter", action="append", default=None)
    analyze_parser.add_argument("--path-filter", action="append", default=None)
    analyze_parser.add_argument("--sort-by", choices=["severity", "path"], default=None)
    analyze_parser.add_argument("--offset", type=int, default=None)
    analyze_parser.add_argument("--limit", type=int, default=None)
    analyze_parser.add_argument("--summary", action="store_true")

    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("--host", default=None, help="API host")
    serve_parser.add_argument("--port", type=int, default=None, help="API port")

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    settings = AppSettings()
    formatter = ReportFormatter()

    if args.command == "analyze":
        overrides = {}
        if args.review_changed_files_only is not None:
            overrides["review_changed_files_only"] = args.review_changed_files_only == "true"
        if args.test_execution_enabled is not None:
            overrides["test_execution_enabled"] = args.test_execution_enabled == "true"
        if args.test_command is not None:
            overrides["test_command"] = args.test_command
        if args.test_timeout_seconds is not None:
            overrides["test_timeout_seconds"] = args.test_timeout_seconds
        settings = settings.model_copy(update=overrides)
        request = AnalyzeRequest(
            repo_ref=args.repo,
            output_format=args.format,
            severity_filter=args.severity_filter,
            agent_filter=args.agent_filter,
            path_filter=args.path_filter,
            sort_by=args.sort_by,
            offset=args.offset,
            limit=args.limit,
        )
        options = ReportQueryOptions(
            severity_filter=request.severity_filter,
            agent_filter=request.agent_filter,
            path_filter=request.path_filter,
            sort_by=request.sort_by,
            offset=request.offset,
            limit=request.limit,
        )
        report = InputPipeline(settings).analyze(args.repo, summary_only=args.summary)
        report = filter_report(report, options)
        report = trim_report(report, options)
        if args.summary:
            print(json.dumps(build_filtered_summary(report, settings, options).model_dump(), indent=2))
            return 0
        output_format = args.format or settings.output_format
        if output_format == "markdown":
            print(formatter.to_markdown(report))
        elif output_format == "sarif":
            print(formatter.to_sarif(report))
        else:
            print(formatter.to_json(report))
        return 0

    if args.command == "serve":
        app = create_app(settings)
        uvicorn.run(app, host=args.host or settings.api_host, port=args.port or settings.api_port)
        return 0

    logging.getLogger(__name__).error("unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main())
