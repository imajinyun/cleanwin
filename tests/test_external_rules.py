from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from pathlib import Path
from typing import Any

from cleanwincli.external_rules import (
    EXTERNAL_RULE_CANDIDATE_SCHEMA,
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
FileKey1=%LocalAppData%\\ExampleBrowser\\User Data\\Default\\Cache|*.*|RECURSE
FileKey2=%UserProfile%\\Documents|*.*|RECURSE
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
        {"candidate_count": 3, "review_required_count": 3, "dangerous_path_count": 2, "execution_enabled_count": 0},
    )
    by_pattern = {candidate["original_pattern"]: candidate for candidate in payload["candidates"]}
    cache_candidate = by_pattern[r"%LocalAppData%\ExampleBrowser\User Data\Default\Cache\*.*"]
    assert_field_values(cache_candidate, {"schema": EXTERNAL_RULE_CANDIDATE_SCHEMA, "review_required": True})
    assert_field_values(cache_candidate["translated_cleanwin_rule"], {"execution_enabled": False, "safe_to_execute": False})
    assert_contains_all(
        by_pattern[r"%UserProfile%\Documents\*.*"]["risk_flags"],
        ["user-document-directory", "wildcard-outside-governed-root"],
    )
    assert_contains_all(by_pattern[r"HKCU\Software\Example\Telemetry"]["risk_flags"], ["registry-pattern"])


def test_cleanerml_translation_keeps_external_rules_untrusted(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    payload = translate_external_rules_text(
        """
<cleaners>
  <cleaner id="example" label="Example Cleaner">
    <action command="delete" path="%LocalAppData%\\Example\\Cache\\*"/>
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
    assert_field_values(payload["source"], {"format": "cleanerml", "upstream_project": "BleachBit/CleanerML"})
    assert_field_values(payload["summary"], {"candidate_count": 2, "execution_enabled_count": 0})
    assert {candidate["provenance"] for candidate in payload["candidates"]} == {"external-untrusted"}
    assert_contains_all(payload["candidates"][1]["risk_flags"], ["user-document-directory"])


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
    samples = assert_schema_samples([EXTERNAL_RULE_TRANSLATION_SCHEMA, EXTERNAL_RULE_CANDIDATE_SCHEMA])
    assert_readonly_report(samples[EXTERNAL_RULE_TRANSLATION_SCHEMA], EXTERNAL_RULE_TRANSLATION_SCHEMA)
    assert_execution_disabled(samples[EXTERNAL_RULE_TRANSLATION_SCHEMA])
    assert_payload_schema(samples[EXTERNAL_RULE_CANDIDATE_SCHEMA], EXTERNAL_RULE_CANDIDATE_SCHEMA)


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
