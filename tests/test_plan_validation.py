"""Unit tests for plan validation and confirmation tokens."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from cleanwincli.models import CATEGORY_TEMP, Candidate, Plan
from cleanwincli.plan_validation import confirmation_token_for_plan, validate_plan_payload


def _make_candidate(path: str, *, safe: bool = True, delete_mode: str = "recycle",
                    category: str = CATEGORY_TEMP, risk: str = "low",
                    requires_admin: bool = False, rationale: str = "regenerated on next run") -> Candidate:
    return Candidate(
        rule_id=f"test.{Path(path).name}",
        path=path,
        category=category,
        size_bytes=100,
        reason="temporary or cache data",
        risk=risk,
        safe_to_delete=safe,
        safe_to_delete_rationale=rationale,
        delete_mode=delete_mode,
        requires_admin=requires_admin,
        identity={"size_bytes": 100, "modified_ns": 1000000000},
    )


def _make_plan(candidates: list[Candidate] | None = None) -> Plan:
    return Plan(
        candidates=candidates or [],
        categories=[CATEGORY_TEMP],
    )


class TestValidatePlanSchema:
    def test_matching_schema_is_valid(self) -> None:
        plan = _make_plan()
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=False)
        assert result["valid"]
        assert result["errors"] == []

    def test_missing_schema_is_rejected(self) -> None:
        plan = _make_plan()
        raw: dict[str, object] = {}
        result = validate_plan_payload(plan, raw, require_context=False)
        assert not result["valid"]
        assert any("Unsupported plan schema" in e for e in result["errors"])

    def test_wrong_schema_is_rejected(self) -> None:
        plan = _make_plan()
        raw = {"schema": "cleanwin.something-else.v1"}
        result = validate_plan_payload(plan, raw, require_context=False)
        assert not result["valid"]
        assert any("Unsupported plan schema" in e for e in result["errors"])


class TestValidatePlanFingerprint:
    def test_mismatched_fingerprint_is_rejected(self, tmp_path: Path) -> None:
        candidate = _make_candidate(str(tmp_path / "stale.tmp"))
        plan = _make_plan([candidate])
        raw = plan.to_dict()
        raw["source_fingerprint"] = "totally-wrong-fingerprint"
        result = validate_plan_payload(plan, raw, require_context=False)
        assert not result["valid"]
        assert any("source_fingerprint does not match" in e for e in result["errors"])


def _plan_with_context(plan: Plan, *, home: str | None = None, user: str | None = None) -> Plan:
    """Create a copy of plan with modified context fields (Plan is frozen)."""
    ctx = plan.context
    new_ctx = type(ctx)(
        hostname=ctx.hostname,
        platform=ctx.platform,
        os_name=ctx.os_name,
        user=user if user is not None else ctx.user,
        home=home if home is not None else ctx.home,
    )
    object.__setattr__(plan, "context", new_ctx)
    return plan


class TestValidatePlanContext:
    def test_home_mismatch_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", "/home/alice")
        monkeypatch.setenv("USERPROFILE", "C:\\Users\\alice")
        monkeypatch.setenv("USERNAME", "alice")
        plan = _plan_with_context(_make_plan(), home="/home/bob", user="alice")
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=True)
        assert not result["valid"]
        assert any("home context does not match" in e for e in result["errors"])

    def test_user_mismatch_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", "/home/alice")
        monkeypatch.setenv("USERPROFILE", "C:\\Users\\alice")
        monkeypatch.setenv("USERNAME", "alice")
        plan = _plan_with_context(_make_plan(), user="bob")
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=True)
        assert not result["valid"]
        assert any("user context does not match" in e for e in result["errors"])

    def test_context_disabled_skips_check(self) -> None:
        plan = _plan_with_context(_make_plan(), home="/somewhere/else", user="someone-else")
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=False)
        assert result["valid"]


class TestValidateCandidateSafety:
    def test_unsafe_candidate_is_rejected(self, tmp_path: Path) -> None:
        candidate = _make_candidate(str(tmp_path / "file.tmp"), safe=False, rationale="")
        plan = _make_plan([candidate])
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=False)
        assert not result["valid"]
        assert any("not marked safe_to_delete" in e for e in result["errors"])

    def test_permanent_delete_mode_rejected(self, tmp_path: Path) -> None:
        candidate = _make_candidate(str(tmp_path / "file.tmp"), delete_mode="permanent")
        plan = _make_plan([candidate])
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=False)
        assert not result["valid"]
        assert any("Unsupported plan delete_mode" in e for e in result["errors"])

    def test_admin_required_rejected(self, tmp_path: Path) -> None:
        candidate = _make_candidate(str(tmp_path / "file.tmp"), requires_admin=True)
        plan = _make_plan([candidate])
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=False)
        assert not result["valid"]
        assert any("Admin-scoped candidate" in e for e in result["errors"])

    def test_high_risk_rejected(self, tmp_path: Path) -> None:
        candidate = _make_candidate(str(tmp_path / "file.tmp"), risk="high")
        plan = _make_plan([candidate])
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=False)
        assert not result["valid"]
        assert any("Only low-risk cache candidates" in e for e in result["errors"])

    def test_missing_rationale_rejected(self, tmp_path: Path) -> None:
        candidate = _make_candidate(str(tmp_path / "file.tmp"), rationale="")
        plan = _make_plan([candidate])
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=False)
        assert not result["valid"]
        assert any("regeneration rationale" in e for e in result["errors"])

    def test_non_executable_category_rejected(self, tmp_path: Path) -> None:
        candidate = _make_candidate(str(tmp_path / "file.tmp"), category="windows-component-clean")
        plan = _make_plan([candidate])
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=False)
        assert not result["valid"]
        assert any("not enabled for controlled low-risk cache execution" in e for e in result["errors"])


class TestValidateIdentity:
    def test_identity_mismatch_detected(self, tmp_path: Path, write_text_file: Callable[[Path, str], Path]) -> None:
        file_path = write_text_file(tmp_path / "stale.tmp", "hello")
        candidate = _make_candidate(str(file_path))
        object.__setattr__(candidate, "identity", {"size_bytes": 999999, "modified_ns": 1})
        plan = _make_plan([candidate])
        raw = plan.to_dict()
        result = validate_plan_payload(plan, raw, require_context=False)
        assert not result["valid"]
        assert any("Filesystem identity mismatch" in e for e in result["errors"])


class TestConfirmationToken:
    def test_token_is_stable_for_same_plan(self) -> None:
        plan = _make_plan()
        raw = plan.to_dict()
        token1 = confirmation_token_for_plan(plan, raw)
        token2 = confirmation_token_for_plan(plan, raw)
        assert token1 == token2
        assert len(token1) == 64

    def test_token_changes_with_fingerprint(self) -> None:
        plan = _make_plan()
        raw1 = plan.to_dict()
        raw2 = dict(raw1, source_fingerprint="different")
        assert confirmation_token_for_plan(plan, raw1) != confirmation_token_for_plan(plan, raw2)

    def test_token_changes_with_candidate_count(self, tmp_path: Path) -> None:
        c1 = _make_candidate(str(tmp_path / "a.tmp"))
        c2 = _make_candidate(str(tmp_path / "b.tmp"))
        p1 = _make_plan([c1])
        p2 = _make_plan([c1, c2])
        assert confirmation_token_for_plan(p1, p1.to_dict()) != confirmation_token_for_plan(p2, p2.to_dict())
