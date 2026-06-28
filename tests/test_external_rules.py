from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from pathlib import Path
from typing import Any

from cleanwincli.external_rules import (
    EXTERNAL_RULE_CANDIDATE_SCHEMA,
    EXTERNAL_RULE_IMPORT_SANDBOX_SCHEMA,
    EXTERNAL_RULE_TRANSLATION_SCHEMA,
    external_rule_translation_sample,
    translate_external_rules_text,
)

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
WriteTextFile = Callable[[Path, str], Path]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertSchemaSamples = Callable[[Sequence[str]], dict[str, JSONPayload]]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]


def test_winapp2_translation_is_report_only_and_marks_dangerous_paths(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    payload = translate_external_rules_text(
        """
[Example Browser Cache *]
LangSecRef=3029
DetectFile=%LocalAppData%\\ExampleBrowser\\User Data\\Default
DetectOS=10.0|
SpecialDetect=DetectWinApp
Warning=Close Example Browser first.
FileKey1=%LocalAppData%\\ExampleBrowser\\User Data\\Default\\Cache|*.*|RECURSE
FileKey2=%UserProfile%\\Documents|*.*|RECURSE
ExcludeKey1=FILE|%LocalAppData%\\ExampleBrowser\\User Data\\Default\\Cache\\Keep
RegKey1=HKCU\\Software\\Example\\Telemetry
""".strip(),
        source_format="winapp2",
        upstream_project="BleachBit/winapp2.ini",
        upstream_rule_id_or_commit="fixture",
        license_name="GPL-3.0-or-later-or-upstream-license-review",
    )

    assert_readonly_report(payload, EXTERNAL_RULE_TRANSLATION_SCHEMA)
    assert_execution_disabled(payload)
    assert_field_values(
        payload["summary"],
        {
            "candidate_count": 3,
            "review_queue_count": 3,
            "review_required_count": 3,
            "dangerous_path_count": 2,
            "execution_enabled_count": 0,
            "unsupported_semantic_count": 9,
        },
    )
    by_pattern = {candidate["original_pattern"]: candidate for candidate in payload["candidates"]}
    cache_candidate = by_pattern[r"%LocalAppData%\ExampleBrowser\User Data\Default\Cache\*.*"]
    assert_field_values(cache_candidate, {"schema": EXTERNAL_RULE_CANDIDATE_SCHEMA, "review_required": True})
    assert_field_values(cache_candidate["translated_cleanwin_rule"], {"execution_enabled": False, "safe_to_execute": False})
    assert_field_values(
        cache_candidate,
        {
            "section_metadata.lang_sec_ref": "3029",
            "section_metadata.detect_count": 1,
            "section_metadata.detect_os_count": 1,
            "section_metadata.special_detect_count": 1,
            "section_metadata.exclude_key_count": 1,
            "warning": "Close Example Browser first.",
        },
    )
    assert_contains_all(cache_candidate["detection"]["detect"], [r"%LocalAppData%\ExampleBrowser\User Data\Default"])
    assert_contains_all(cache_candidate["unsupported_semantics"], ["DetectOS", "SpecialDetect", "Warning"])
    assert_contains_all(
        [exclude["pattern"] for exclude in cache_candidate["exclusions"]],
        [r"FILE|%LocalAppData%\ExampleBrowser\User Data\Default\Cache\Keep"],
    )
    assert_contains_all(
        by_pattern[r"%UserProfile%\Documents\*.*"]["risk_flags"],
        ["user-document-directory", "wildcard-outside-governed-root"],
    )
    assert_contains_all(by_pattern[r"HKCU\Software\Example\Telemetry"]["risk_flags"], ["registry-pattern"])


def test_external_rule_translation_includes_import_sandbox_contract(
    assert_payload_schema: AssertPayloadSchema,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    payload = translate_external_rules_text(
        """
[Example Browser Cache *]
FileKey1=%LocalAppData%\\ExampleBrowser\\User Data\\Default\\Cache|*.*|RECURSE
FileKey2=%UserProfile%\\Documents|*.*|RECURSE
SpecialDetect=DetectWinApp
RegKey1=HKCU\\Software\\Example\\Telemetry
""".strip(),
        source_format="winapp2",
        upstream_project="BleachBit/winapp2.ini",
        upstream_rule_id_or_commit="fixture",
    )

    sandbox = assert_payload_schema(payload["import_sandbox"], EXTERNAL_RULE_IMPORT_SANDBOX_SCHEMA)
    assert_field_values(
        sandbox,
        {
            "destructive": False,
            "dry_run": True,
            "execution_enabled": False,
            "default_import_mode": "report-only",
            "external_rule_pack_candidate.source": "external-untrusted",
            "external_rule_pack_candidate.review_status": "unreviewed",
            "external_rule_pack_candidate.rule_count": 3,
            "validation.owner_required": True,
            "validation.rationale_required": True,
            "validation.schema_validation_required": True,
            "validation.default_execution_enabled": False,
            "summary.candidate_count": 3,
            "summary.dangerous_path_count": 2,
            "summary.unsupported_semantic_count": 3,
            "summary.owner_missing_count": 0,
            "summary.rationale_missing_count": 0,
        },
    )
    assert_contains_all(
        sandbox["promotion_blockers"],
        [
            "external-untrusted-provenance",
            "owner-review-required",
            "fixture-coverage-required",
            "dangerous-path-review-required",
            "unsupported-semantics-review-required",
        ],
    )
    assert_contains_all(
        sandbox["dangerous_path_scan"]["flag_counts"],
        ["registry-pattern", "user-document-directory", "wildcard-outside-governed-root"],
    )


def test_cleanerml_translation_keeps_external_rules_untrusted(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    payload = translate_external_rules_text(
        """
<cleaners>
  <cleaner id="example" label="Example Cleaner" category="Applications">
    <option id="cache" label="Cache"/>
    <detect path="%LocalAppData%\\Example"/>
    <exclude path="%LocalAppData%\\Example\\Cache\\Keep"/>
    <action command="delete" path="%LocalAppData%\\Example\\Cache\\*"/>
    <action command="wipe" regex="%LocalAppData%\\Example\\Logs\\.*"/>
    <action command="delete" path="%UserProfile%\\Downloads\\*"/>
  </cleaner>
</cleaners>
""".strip(),
        source_format="cleanerml",
        upstream_project="BleachBit/CleanerML",
        upstream_rule_id_or_commit="fixture",
        license_name="GPL-3.0-or-later-or-upstream-license-review",
    )

    assert_readonly_report(payload, EXTERNAL_RULE_TRANSLATION_SCHEMA)
    assert_execution_disabled(payload)
    assert_field_values(
        payload["source"],
        {
            "format": "cleanerml",
            "upstream_project": "BleachBit/CleanerML",
            "import_batch_id": payload["import_sandbox"]["import_batch_id"],
        },
    )
    assert_field_values(
        payload["summary"],
        {"candidate_count": 3, "review_queue_count": 3, "execution_enabled_count": 0, "unsupported_semantic_count": 2},
    )
    assert {candidate["provenance"] for candidate in payload["candidates"]} == {"external-untrusted"}
    assert_field_values(
        payload["candidates"][0],
        {
            "section_metadata.category": "Applications",
            "section_metadata.option_count": 1,
            "section_metadata.detect_count": 1,
            "section_metadata.exclude_count": 1,
        },
    )
    assert_contains_all(payload["candidates"][1]["unsupported_semantics"], ["action-command:wipe", "action-regex"])
    assert_contains_all(payload["candidates"][2]["risk_flags"], ["user-document-directory"])


def test_external_rule_import_sandbox_builds_review_queue_and_provenance_index(
    assert_field_values: AssertFieldValues,
    assert_contains_all: AssertContainsAll,
    assert_execution_disabled: AssertExecutionDisabled,
) -> None:
    payload = translate_external_rules_text(
        """
[Example Browser Cache *]
SpecialDetect=DetectWinApp
FileKey1=%LocalAppData%\\ExampleBrowser\\User Data\\Default\\Cache|*.*|RECURSE
FileKey2=%UserProfile%\\Documents|*.*|RECURSE
""".strip(),
        source_format="winapp2",
        upstream_project="BleachBit/winapp2.ini",
        upstream_rule_id_or_commit="fixture",
        license_name="GPL-3.0-or-later-or-upstream-license-review",
    )
    sandbox = payload["import_sandbox"]
    review_queue = sandbox["review_queue"]
    provenance = sandbox["provenance_index"]

    assert_field_values(
        sandbox,
        {
            "import_batch_id": payload["source"]["import_batch_id"],
            "source_hash": payload["source"]["source_hash"],
            "summary.review_queue_count": 2,
            "provenance_index.provenance_counts.translated-winapp2": 2,
            "provenance_index.provenance_counts.external-untrusted": 2,
            "provenance_index.promotion_effect.external_untrusted_blocks_execution": True,
            "provenance_index.promotion_effect.execution_enabled": False,
        },
    )
    assert len(payload["source"]["source_hash"]) == 64
    assert payload["source"]["import_batch_id"].startswith("external-winapp2-")
    assert_execution_disabled(review_queue[0])
    assert_field_values(
        review_queue[0],
        {
            "schema": "cleanwin.external-rule-review-queue-item.v1",
            "review_status": "queued",
            "reviewer": "cleanwin-maintainer-required",
            "promotion_allowed": False,
        },
    )
    assert_contains_all(
        review_queue[0]["promotion_blockers"],
        ["external-untrusted-provenance", "owner-review-required", "fixture-coverage-required"],
    )
    assert_contains_all(provenance["provenance_counts"], ["builtin", "translated-winapp2", "manual-reviewed", "external-untrusted"])


def test_external_rule_translate_cli_reads_local_catalog(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    cleanwin_json: CleanWinJSON,
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_field_values: AssertFieldValues,
) -> None:
    source = write_text_file(
        tmp_path / "winapp2.ini",
        """
[Example Cache *]
FileKey1=%LocalAppData%\\Example\\Cache|*.*|RECURSE
""".strip(),
    )

    payload = cleanwin_json(
        "external-rule-translate",
        "--input",
        str(source),
        "--format",
        "winapp2",
        "--upstream-ref",
        "test-ref",
        "--license",
        "GPL-3.0-or-later-or-upstream-license-review",
    )

    assert_readonly_report(payload, EXTERNAL_RULE_TRANSLATION_SCHEMA)
    assert_execution_disabled(payload)
    assert_field_values(payload["source"], {"path": str(source), "upstream_rule_id_or_commit": "test-ref"})
    assert_field_values(payload["summary"], {"candidate_count": 1, "review_required_count": 1})


def test_external_rule_translation_schema_samples_are_registered(
    assert_schema_samples: AssertSchemaSamples,
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    samples = assert_schema_samples(
        [EXTERNAL_RULE_TRANSLATION_SCHEMA, EXTERNAL_RULE_CANDIDATE_SCHEMA, EXTERNAL_RULE_IMPORT_SANDBOX_SCHEMA]
    )
    assert_readonly_report(samples[EXTERNAL_RULE_TRANSLATION_SCHEMA], EXTERNAL_RULE_TRANSLATION_SCHEMA)
    assert_execution_disabled(samples[EXTERNAL_RULE_TRANSLATION_SCHEMA])
    assert_payload_schema(samples[EXTERNAL_RULE_CANDIDATE_SCHEMA], EXTERNAL_RULE_CANDIDATE_SCHEMA)
    assert_readonly_report(samples[EXTERNAL_RULE_IMPORT_SANDBOX_SCHEMA], EXTERNAL_RULE_IMPORT_SANDBOX_SCHEMA)
    assert_execution_disabled(samples[EXTERNAL_RULE_IMPORT_SANDBOX_SCHEMA])


def test_external_rule_translation_sample_matches_contract(
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    sample = external_rule_translation_sample()
    assert_field_values(sample["promotion_gate"], {"requires_owner_review": True, "execution_enabled": False})
    assert_contains_all(
        sample["candidates"][0]["translated_cleanwin_rule"],
        ["owner", "category", "default_path", "sensitive_exclusions", "official_cleanup_command", "rationale"],
    )
