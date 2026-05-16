from __future__ import annotations

import ast
from pathlib import Path

from src.agents.base import BaseReviewAgent
from src.common.settings import AppSettings
from src.input.service import InputPipeline


def test_security_and_style_agents_report_expected_issues(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "import os\n"
        "import pickle\n\n"
        "password = 'secret123'\n\n"
        "class bad_name:\n"
        "    pass\n\n"
        "def BadFunction(first, second, third, fourth, fifth, sixth):\n"
        "    os.system('ls')\n"
        "    pickle.loads(data)\n"
        "    return eval('1 + 1')\n",
        encoding="utf-8",
    )

    report = InputPipeline(AppSettings()).analyze(str(repo))
    rule_ids = {issue.rule_id for issue in report.issues}

    assert "security.hardcoded-secret" in rule_ids
    assert "security.dynamic-execution" in rule_ids
    assert "security.insecure-deserialization" in rule_ids
    assert "style.function-name" in rule_ids
    assert "style.class-name" in rule_ids
    assert "style.too-many-parameters" in rule_ids


def test_security_agent_reports_sql_yaml_tempfile_and_random_risks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "import random\n"
        "import tempfile\n"
        "import yaml\n\n"
        "def run(user_id):\n"
        "    query = 'SELECT * FROM users WHERE id=' + user_id\n"
        "    yaml.load('a: 1')\n"
        "    tempfile.mktemp()\n"
        "    return random.randint(1, 9)\n",
        encoding="utf-8",
    )

    report = InputPipeline(AppSettings()).analyze(str(repo))
    rule_ids = {issue.rule_id for issue in report.issues}

    assert "security.sql-string-concat" in rule_ids
    assert "security.unsafe-yaml-load" in rule_ids
    assert "security.tempfile-mktemp" in rule_ids
    assert "security.weak-random" in rule_ids


def test_structure_agent_reports_cycles(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("import b\n", encoding="utf-8")
    (repo / "b.py").write_text("import a\n", encoding="utf-8")

    report = InputPipeline(AppSettings()).analyze(str(repo))
    cycle_issues = [issue for issue in report.issues if issue.rule_id == "structure.circular-dependency"]

    assert len(cycle_issues) == 1
    assert "a.py -> b.py -> a.py" in cycle_issues[0].evidence[0]


def test_structure_agent_reports_complexity_and_unused_imports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "import os\n"
        "\n"
        "def run(value):\n"
        "    if value > 0:\n"
        "        pass\n"
        "    if value > 1:\n"
        "        pass\n"
        "    if value > 2:\n"
        "        pass\n"
        "    if value > 3:\n"
        "        pass\n"
        "    if value > 4:\n"
        "        pass\n"
        "    if value > 5:\n"
        "        pass\n"
        "    if value > 6:\n"
        "        pass\n"
        "    if value > 7:\n"
        "        pass\n"
        "    if value > 8:\n"
        "        pass\n"
        "    return value\n",
        encoding="utf-8",
    )

    report = InputPipeline(AppSettings()).analyze(str(repo))
    rule_ids = {issue.rule_id for issue in report.issues}

    assert "structure.complex-function" in rule_ids
    assert "structure.unused-import" in rule_ids


def test_structure_agent_reports_unused_symbols(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "class Helper:\n"
        "    pass\n\n"
        "def helper_function():\n"
        "    return 1\n\n"
        "def run():\n"
        "    return 0\n",
        encoding="utf-8",
    )

    report = InputPipeline(AppSettings()).analyze(str(repo))
    rule_ids = {issue.rule_id for issue in report.issues}

    assert "structure.unused-function" in rule_ids
    assert "structure.unused-class" in rule_ids


def test_structure_agent_avoids_unused_symbol_noise_in_single_file_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "def helper_function():\n"
        "    return 1\n\n"
        "def run():\n"
        "    return helper_function()\n",
        encoding="utf-8",
    )

    report = InputPipeline(AppSettings()).analyze(str(repo))
    rule_ids = {issue.rule_id for issue in report.issues}

    assert "structure.unused-function" not in rule_ids


def test_test_agent_reports_missing_targeted_test(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "service.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_other.py").write_text("def test_other():\n    assert True\n", encoding="utf-8")

    report = InputPipeline(AppSettings()).analyze(str(repo))
    rule_ids = {issue.rule_id for issue in report.issues}

    assert "test.missing-targeted-test" in rule_ids


def test_test_agent_skips_init_files_for_targeted_mapping(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    package_dir = repo / "pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")

    report = InputPipeline(AppSettings()).analyze(str(repo))
    rule_ids = [issue.rule_id for issue in report.issues if issue.path == "pkg/__init__.py"]

    assert "test.missing-targeted-test" not in rule_ids


def test_performance_agent_reports_loop_io_and_repeated_len(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "import requests\n\n"
        "def run(items):\n"
        "    for item in items:\n"
        "        if len(items) > 0 and len(items) > 1:\n"
        "            requests.get('https://example.com')\n"
        "    return items\n",
        encoding="utf-8",
    )

    report = InputPipeline(AppSettings()).analyze(str(repo))
    rule_ids = {issue.rule_id for issue in report.issues}

    assert "performance.loop-io" in rule_ids
    assert "performance.repeated-len-call" in rule_ids


def test_test_agent_injects_test_execution_result(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    report = InputPipeline(
        AppSettings(
            test_execution_enabled=True,
            test_command="pytest",
            test_timeout_seconds=10,
        )
    ).analyze(str(repo))

    assert report.feedback is not None
    assert report.feedback.test_summary["status"] == "passed"


def test_agents_share_cached_python_ast_parsing(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "import os\n"
        "def run(items):\n"
        "    for item in items:\n"
        "        if len(items) > 0 and len(items) > 1:\n"
        "            os.system('ls')\n"
        "    return items\n",
        encoding="utf-8",
    )

    parse_calls = {"count": 0}
    original_parse = ast.parse

    def counting_parse(*args, **kwargs):
        parse_calls["count"] += 1
        return original_parse(*args, **kwargs)

    monkeypatch.setattr(ast, "parse", counting_parse)

    InputPipeline(AppSettings(report_only_new_issues=False)).analyze(str(repo))

    assert parse_calls["count"] == 1


def test_input_pipeline_clears_repo_cache_before_analysis(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    repo_path = str(repo)

    BaseReviewAgent.warm_file_cache(repo_path, "stale.py", "oldhash", "print('stale')")
    BaseReviewAgent.warm_ast_cache(repo_path, "stale.py", "oldhash", ast.parse("print('stale')"))

    (repo / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    InputPipeline(AppSettings(report_only_new_issues=False)).analyze(str(repo))

    assert (repo_path, "stale.py", "oldhash") not in BaseReviewAgent._content_cache
    assert (repo_path, "stale.py", "oldhash") not in BaseReviewAgent._ast_cache


def test_agent_shared_cache_enforces_entry_limit() -> None:
    BaseReviewAgent._content_cache.clear()
    BaseReviewAgent._ast_cache.clear()
    BaseReviewAgent.set_cache_max_entries(2)

    BaseReviewAgent.warm_file_cache("repo-a", "a.py", "1", "a")
    BaseReviewAgent.warm_file_cache("repo-b", "b.py", "2", "b")
    BaseReviewAgent.warm_file_cache("repo-c", "c.py", "3", "c")

    BaseReviewAgent.warm_ast_cache("repo-a", "a.py", "1", ast.parse("a = 1"))
    BaseReviewAgent.warm_ast_cache("repo-b", "b.py", "2", ast.parse("b = 2"))
    BaseReviewAgent.warm_ast_cache("repo-c", "c.py", "3", ast.parse("c = 3"))

    assert len(BaseReviewAgent._content_cache) == 2
    assert len(BaseReviewAgent._ast_cache) == 2
    assert ("repo-a", "a.py", "1") not in BaseReviewAgent._content_cache
    assert ("repo-a", "a.py", "1") not in BaseReviewAgent._ast_cache

    BaseReviewAgent.set_cache_max_entries(AppSettings().agent_cache_max_entries)


def test_input_pipeline_reports_cache_metrics_and_executed_agents(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "import os\n"
        "def run(items):\n"
        "    for item in items:\n"
        "        if len(items) > 0 and len(items) > 1:\n"
        "            os.system('ls')\n"
        "    return items\n",
        encoding="utf-8",
    )

    report = InputPipeline(AppSettings(report_only_new_issues=False)).analyze(str(repo))

    assert report.metadata.cache_ast_hits >= 1
    assert report.metadata.cache_ast_misses == 0
    assert report.metadata.cache_content_hits >= 0
    assert report.metadata.cache_content_misses == 0
    assert report.metadata.executed_agents == ["structure", "performance", "security", "style", "test"]
