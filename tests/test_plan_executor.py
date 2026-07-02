"""Unit tests for plan executor — execution safety gates."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cleanwincli.ai_schema import CONFIRMATION_PHRASE
from cleanwincli.models import CATEGORY_TEMP, Candidate, Plan
from cleanwincli.plan_executor import execute_plan, execution_result_summary
from cleanwincli.plan_validation import confirmation_token_for_plan


def _make_candidate(path: str) -> Candidate:
    return Candidate(
        rule_id=f"test.{Path(path).name}",
        path=path,
        category=CATEGORY_TEMP,
        size_bytes=100,
        reason="temporary or cache data",
        risk="low",
        safe_to_delete=True,
        safe_to_delete_rationale="regenerated on next run",
        delete_mode="recycle",
        requires_admin=False,
        identity={"size_bytes": 100, "modified_ns": 1000000000},
    )


def _make_plan(tmp_path: Path, write_text_file: Callable[[Path, str], Path]) -> tuple[Plan, dict[str, object]]:
    file_path = write_text_file(tmp_path / "stale.tmp", "x")
    from cleanwincli.identity import capture_filesystem_identity

    candidate = _make_candidate(str(file_path))
    identity = capture_filesystem_identity(file_path)
    object.__setattr__(candidate, "identity", identity)
    plan = Plan(candidates=[candidate], categories=[CATEGORY_TEMP])
    raw = plan.to_dict()
    return plan, raw


class TestExecutionResultSummary:
    def test_empty_results(self) -> None:
        summary = execution_result_summary([])
        assert summary["result_count"] == 0
        assert summary["status_counts"] == {}

    def test_counts_statuses(self) -> None:
        results = [
            {"status": "dry-run", "path": "/a"},
            {"status": "dry-run", "path": "/b"},
            {"status": "missing", "path": "/c"},
        ]
        summary = execution_result_summary(results)
        assert summary["result_count"] == 3
        assert summary["status_counts"] == {"dry-run": 2, "missing": 1}
        assert list(summary["status_counts"].keys()) == sorted(summary["status_counts"].keys())


class TestExecutePlanDryRun:
    def test_dry_run_returns_dry_run_status(self, tmp_path: Path, write_text_file: Callable[[Path, str], Path]) -> None:
        plan, raw = _make_plan(tmp_path, write_text_file)
        result = execute_plan(
            plan,
            execute=False,
            yes=False,
            require_context=False,
            raw_payload=raw,
            operation_log=None,
            trash_root=tmp_path / "trash",
        )
        assert result["schema"] == "cleanwin.execute.v1"
        assert not result["executed"]
        assert result["dry_run"] is True
        assert all(r["status"] == "dry-run" for r in result["results"])
        assert len(result["results"]) == 1
        assert "confirmation" in result
        assert result["confirmation"]["required_phrase"] == CONFIRMATION_PHRASE
        assert len(result["confirmation"]["confirmation_token"]) == 64
        file_path = tmp_path / "stale.tmp"
        assert file_path.exists()

    def test_invalid_plan_returns_empty_results(self, tmp_path: Path, write_text_file: Callable[[Path, str], Path]) -> None:
        plan, raw = _make_plan(tmp_path, write_text_file)
        raw["schema"] = "wrong-schema"
        result = execute_plan(
            plan,
            execute=False,
            yes=False,
            require_context=False,
            raw_payload=raw,
            operation_log=None,
            trash_root=tmp_path / "trash",
        )
        assert not result["executed"]
        assert not result["validation"]["valid"]
        assert result["results"] == []


class TestExecutePlanGates:
    def test_requires_yes_flag(self, tmp_path: Path, write_text_file: Callable[[Path, str], Path]) -> None:
        plan, raw = _make_plan(tmp_path, write_text_file)
        result = execute_plan(
            plan,
            execute=True,
            yes=False,
            require_context=False,
            raw_payload=raw,
            operation_log=None,
            trash_root=tmp_path / "trash",
        )
        assert not result["executed"]
        assert "requires --yes" in result["error"]

    def test_requires_operation_log(self, tmp_path: Path, write_text_file: Callable[[Path, str], Path]) -> None:
        plan, raw = _make_plan(tmp_path, write_text_file)
        result = execute_plan(
            plan,
            execute=True,
            yes=True,
            require_context=False,
            raw_payload=raw,
            operation_log=None,
            trash_root=tmp_path / "trash",
        )
        assert not result["executed"]
        assert "requires --operation-log" in result["error"]

    def test_requires_confirmation_phrase(self, tmp_path: Path, write_text_file: Callable[[Path, str], Path]) -> None:
        plan, raw = _make_plan(tmp_path, write_text_file)
        op_log = tmp_path / "ops.jsonl"
        result = execute_plan(
            plan,
            execute=True,
            yes=True,
            require_context=False,
            raw_payload=raw,
            operation_log=op_log,
            trash_root=tmp_path / "trash",
            confirmation_phrase="wrong phrase",
        )
        assert not result["executed"]
        assert "exact confirmation phrase" in result["error"]

    def test_requires_confirmation_token(self, tmp_path: Path, write_text_file: Callable[[Path, str], Path]) -> None:
        plan, raw = _make_plan(tmp_path, write_text_file)
        op_log = tmp_path / "ops.jsonl"
        result = execute_plan(
            plan,
            execute=True,
            yes=True,
            require_context=False,
            raw_payload=raw,
            operation_log=op_log,
            trash_root=tmp_path / "trash",
            confirmation_phrase=CONFIRMATION_PHRASE,
            confirmation_token="wrong-token",
        )
        assert not result["executed"]
        assert "matching dry-run confirmation token" in result["error"]

    def test_valid_gates_pass_dry_run_does_not_delete(self, tmp_path: Path, write_text_file: Callable[[Path, str], Path]) -> None:
        plan, raw = _make_plan(tmp_path, write_text_file)
        op_log = tmp_path / "ops.jsonl"
        token = confirmation_token_for_plan(plan, raw)
        result = execute_plan(
            plan,
            execute=False,
            yes=True,
            require_context=False,
            raw_payload=raw,
            operation_log=op_log,
            trash_root=tmp_path / "trash",
            confirmation_phrase=CONFIRMATION_PHRASE,
            confirmation_token=token,
        )
        assert not result["executed"]
        file_path = tmp_path / "stale.tmp"
        assert file_path.exists()

    def test_invalid_plan_blocks_execution(self, tmp_path: Path, write_text_file: Callable[[Path, str], Path]) -> None:
        plan, raw = _make_plan(tmp_path, write_text_file)
        raw["schema"] = "wrong"
        op_log = tmp_path / "ops.jsonl"
        token = confirmation_token_for_plan(plan, raw)
        result = execute_plan(
            plan,
            execute=True,
            yes=True,
            require_context=False,
            raw_payload=raw,
            operation_log=op_log,
            trash_root=tmp_path / "trash",
            confirmation_phrase=CONFIRMATION_PHRASE,
            confirmation_token=token,
        )
        assert not result["executed"]
        assert not result["validation"]["valid"]
