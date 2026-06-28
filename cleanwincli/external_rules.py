"""Read-only translators for external Windows cleaner rule catalogs."""

from __future__ import annotations

import configparser
import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXTERNAL_RULE_TRANSLATION_SCHEMA = "cleanwin.external-rule-translation.v1"
EXTERNAL_RULE_CANDIDATE_SCHEMA = "cleanwin.external-rule-candidate.v1"
EXTERNAL_RULE_IMPORT_SANDBOX_SCHEMA = "cleanwin.external-rule-import-sandbox.v1"

SUPPORTED_FORMATS = ("auto", "winapp2", "cleanerml")
DEFAULT_LICENSE = "external-review-required"
DEFAULT_UPSTREAM_COMMIT = "local-file"
_SAFE_ROOT_TOKENS = (
    "%appdata%",
    "%localappdata%",
    "%programdata%",
    "%temp%",
    "%tmp%",
    "%userprofile%\\appdata\\",
    "c:\\users\\*\\appdata\\",
)
_USER_DOCUMENT_TOKENS = (
    "%userprofile%\\documents",
    "%userprofile%\\desktop",
    "%userprofile%\\downloads",
    "%userprofile%\\pictures",
    "%userprofile%\\videos",
    "%userprofile%\\music",
    "c:\\users\\*\\documents",
    "c:\\users\\*\\desktop",
    "c:\\users\\*\\downloads",
)
_BROWSER_PROFILE_ROOT_TOKENS = (
    "google\\chrome\\user data\\default",
    "microsoft\\edge\\user data\\default",
    "mozilla\\firefox\\profiles",
)
_COMMAND_TOKENS = ("cmd.exe", "powershell", "reg.exe", "reg delete", "schtasks", "sc.exe", "dism.exe")


@dataclass(frozen=True)
class ExternalRuleSource:
    source_format: str
    upstream_project: str
    upstream_rule_id_or_commit: str
    license: str
    source_hash: str
    import_batch_id: str
    source_path: str | None = None


@dataclass(frozen=True)
class _RawExternalRule:
    rule_id: str
    title: str
    original_pattern: str
    owner: str
    category_hint: str
    action: str
    section_metadata: dict[str, Any]
    detection: dict[str, Any]
    exclusions: list[dict[str, str]]
    unsupported_semantics: list[str]
    warning: str = ""


class _CasePreservingConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


def _normalise_format(source_format: str, text: str) -> str:
    if source_format not in SUPPORTED_FORMATS:
        raise ValueError(f"unsupported external rule format: {source_format}")
    if source_format != "auto":
        return source_format
    stripped = text.lstrip()
    if stripped.startswith("<"):
        return "cleanerml"
    return "winapp2"


def _normalise_path(pattern: str) -> str:
    return pattern.replace("/", "\\").strip()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "external-rule"


def _category_for(pattern: str, hint: str) -> str:
    haystack = f"{pattern} {hint}".lower()
    if any(token in haystack for token in ("cache", "cached", "temporary internet files", "gpu cache")):
        return "external-cache-candidate"
    if any(token in haystack for token in ("log", "logs", "crash", "dump")):
        return "external-log-candidate"
    if any(token in haystack for token in ("cookie", "history", "session", "password")):
        return "external-sensitive-profile-candidate"
    return "external-cleaner-candidate"


def _risk_flags(pattern: str, action: str) -> list[str]:
    normalised = _normalise_path(pattern).lower()
    flags: list[str] = []
    if action and action.lower() not in {"delete", "deletefiles", "deletepath", "filekey"}:
        flags.append("non-file-cleaner-action")
    if normalised.startswith("hkey_") or normalised.startswith("hkcu\\") or normalised.startswith("hklm\\"):
        flags.append("registry-pattern")
    if any(token in normalised for token in _COMMAND_TOKENS):
        flags.append("raw-command-token")
    if any(token in normalised for token in _USER_DOCUMENT_TOKENS):
        flags.append("user-document-directory")
    if any(token in normalised for token in _BROWSER_PROFILE_ROOT_TOKENS) and not any(
        cache_token in normalised for cache_token in ("cache", "code cache", "gpucache", "startupcache")
    ):
        flags.append("browser-profile-root")
    if "*" in normalised and not any(token in normalised for token in _SAFE_ROOT_TOKENS):
        flags.append("wildcard-outside-governed-root")
    if not any(token in normalised for token in _SAFE_ROOT_TOKENS) and not normalised.startswith("hkey_"):
        flags.append("ungoverned-root")
    return sorted(set(flags))


def _sensitive_exclusions(pattern: str) -> list[str]:
    normalised = pattern.lower()
    exclusions = [
        "cookies",
        "login data",
        "password stores",
        "sessions",
        "profile root",
        "sync state",
        "user documents",
    ]
    if "cache" in normalised or "log" in normalised:
        return exclusions
    return [*exclusions, "registry values unless export and rollback metadata exist"]


def _candidate_from_raw(raw: _RawExternalRule, source: ExternalRuleSource) -> dict[str, Any]:
    flags = _risk_flags(raw.original_pattern, raw.action)
    category = _category_for(raw.original_pattern, raw.category_hint)
    cleanwin_rule_id = f"external.{source.source_format}.{_slug(raw.owner)}.{_slug(raw.rule_id)}"
    translated_rule = {
        "rule_id": cleanwin_rule_id,
        "owner": raw.owner,
        "category": category,
        "default_path": _normalise_path(raw.original_pattern),
        "official_cleanup_command": "Use the application's built-in cleanup or storage settings first; cleanwin import remains report-only.",
        "rationale": "External cleaner definitions require cleanwin owner review, fixture coverage, and sensitive-data exclusions before promotion.",
        "sensitive_exclusions": _sensitive_exclusions(raw.original_pattern),
        "review_required": True,
        "execution_enabled": False,
        "safe_to_execute": False,
    }
    return {
        "schema": EXTERNAL_RULE_CANDIDATE_SCHEMA,
        "source_format": source.source_format,
        "upstream_project": source.upstream_project,
        "upstream_rule_id_or_commit": source.upstream_rule_id_or_commit,
        "license": source.license,
        "external_rule_id": raw.rule_id,
        "title": raw.title,
        "original_pattern": raw.original_pattern,
        "action": raw.action,
        "section_metadata": raw.section_metadata,
        "detection": raw.detection,
        "exclusions": raw.exclusions,
        "unsupported_semantics": raw.unsupported_semantics,
        "warning": raw.warning,
        "translated_cleanwin_rule": translated_rule,
        "review_required": True,
        "execution_enabled": False,
        "dangerous_path": bool(flags),
        "risk_flags": flags,
        "provenance": "external-untrusted",
    }


def _dangerous_path_scan(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    flag_counts: dict[str, int] = {}
    dangerous_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        flags = [str(flag) for flag in candidate.get("risk_flags", [])]
        for flag in flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
        if candidate.get("dangerous_path"):
            dangerous_candidates.append(
                {
                    "external_rule_id": candidate.get("external_rule_id"),
                    "original_pattern": candidate.get("original_pattern"),
                    "risk_flags": flags,
                }
            )
    return {
        "schema": "cleanwin.external-rule-dangerous-path-scan.v1",
        "dangerous_path_count": len(dangerous_candidates),
        "flag_counts": dict(sorted(flag_counts.items())),
        "dangerous_candidates": dangerous_candidates,
    }


def _external_rule_pack_candidate(candidates: list[dict[str, Any]], source: ExternalRuleSource) -> dict[str, Any]:
    return {
        "schema": "cleanwin.external-rule-pack-candidate.v1",
        "pack_id": f"external.{source.source_format}.{_slug(source.upstream_project)}",
        "version": source.upstream_rule_id_or_commit,
        "source": "external-untrusted",
        "review_status": "unreviewed",
        "source_format": source.source_format,
        "upstream_project": source.upstream_project,
        "source_hash": source.source_hash,
        "import_batch_id": source.import_batch_id,
        "license": source.license,
        "rule_count": len(candidates),
        "rule_ids": [str(candidate.get("translated_cleanwin_rule", {}).get("rule_id")) for candidate in candidates],
        "execution_enabled": False,
        "promotion_allowed": False,
    }


def _review_queue(candidates: list[dict[str, Any]], source: ExternalRuleSource) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for candidate in candidates:
        translated = candidate.get("translated_cleanwin_rule", {})
        blockers = [
            "external-untrusted-provenance",
            "owner-review-required",
            "fixture-coverage-required",
            "execution-disabled-by-default",
        ]
        if candidate.get("dangerous_path"):
            blockers.append("dangerous-path-review-required")
        if candidate.get("unsupported_semantics"):
            blockers.append("unsupported-semantics-review-required")
        queue.append(
            {
                "schema": "cleanwin.external-rule-review-queue-item.v1",
                "import_batch_id": source.import_batch_id,
                "source_hash": source.source_hash,
                "external_rule_id": candidate.get("external_rule_id"),
                "translated_rule_id": translated.get("rule_id"),
                "source_format": source.source_format,
                "provenance": candidate.get("provenance"),
                "owner": translated.get("owner") or "",
                "reviewer": "cleanwin-maintainer-required",
                "license": source.license,
                "review_status": "queued",
                "dangerous_path": bool(candidate.get("dangerous_path")),
                "risk_flags": list(candidate.get("risk_flags", [])),
                "unsupported_semantics": list(candidate.get("unsupported_semantics", [])),
                "promotion_blockers": blockers,
                "execution_enabled": False,
                "promotion_allowed": False,
            }
        )
    return queue


def _provenance_index(candidates: list[dict[str, Any]], source: ExternalRuleSource) -> dict[str, Any]:
    provenance_counts: dict[str, int] = {"builtin": 0, "translated-winapp2": 0, "translated-cleanerml": 0, "manual-reviewed": 0, "external-untrusted": 0}
    source_format_counts: dict[str, int] = {}
    review_status_counts: dict[str, int] = {"queued": len(candidates), "manual-reviewed": 0, "blocked": 0}
    translated_key = "translated-winapp2" if source.source_format == "winapp2" else "translated-cleanerml"
    provenance_counts[translated_key] = len(candidates)
    provenance_counts["external-untrusted"] = len(candidates)
    source_format_counts[source.source_format] = len(candidates)
    return {
        "schema": "cleanwin.external-rule-provenance-index.v1",
        "import_batch_id": source.import_batch_id,
        "source_hash": source.source_hash,
        "source_format": source.source_format,
        "upstream_project": source.upstream_project,
        "license": source.license,
        "provenance_counts": provenance_counts,
        "source_format_counts": source_format_counts,
        "review_status_counts": review_status_counts,
        "promotion_effect": {
            "external_untrusted_blocks_execution": True,
            "translated_rules_require_manual_review": True,
            "manual_review_required_before_builtin_pack": True,
            "execution_enabled": False,
        },
    }


def _import_sandbox(candidates: list[dict[str, Any]], source: ExternalRuleSource) -> dict[str, Any]:
    owner_missing_count = sum(1 for candidate in candidates if not str(candidate.get("translated_cleanwin_rule", {}).get("owner") or ""))
    rationale_missing_count = sum(1 for candidate in candidates if not str(candidate.get("translated_cleanwin_rule", {}).get("rationale") or ""))
    dangerous_path_scan = _dangerous_path_scan(candidates)
    unsupported_semantic_count = sum(len(candidate.get("unsupported_semantics", [])) for candidate in candidates)
    review_queue = _review_queue(candidates, source)
    provenance_index = _provenance_index(candidates, source)
    promotion_blockers = [
        "external-untrusted-provenance",
        "owner-review-required",
        "fixture-coverage-required",
        "schema-validation-required",
        "execution-disabled-by-default",
    ]
    if dangerous_path_scan["dangerous_path_count"]:
        promotion_blockers.append("dangerous-path-review-required")
    if unsupported_semantic_count:
        promotion_blockers.append("unsupported-semantics-review-required")
    return {
        "schema": EXTERNAL_RULE_IMPORT_SANDBOX_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "execution_enabled": False,
        "default_import_mode": "report-only",
        "import_batch_id": source.import_batch_id,
        "source_hash": source.source_hash,
        "supported_formats": ["winapp2", "cleanerml"],
        "allowed_sources": ["local-file"],
        "external_rule_pack_candidate": _external_rule_pack_candidate(candidates, source),
        "validation": {
            "schema_validation_required": True,
            "owner_required": True,
            "rationale_required": True,
            "sensitive_exclusions_required": True,
            "fixture_coverage_required": True,
            "quality_score_required": True,
            "default_execution_enabled": False,
        },
        "dangerous_path_scan": dangerous_path_scan,
        "review_queue": review_queue,
        "provenance_index": provenance_index,
        "summary": {
            "candidate_count": len(candidates),
            "review_queue_count": len(review_queue),
            "dangerous_path_count": dangerous_path_scan["dangerous_path_count"],
            "unsupported_semantic_count": unsupported_semantic_count,
            "owner_missing_count": owner_missing_count,
            "rationale_missing_count": rationale_missing_count,
            "execution_enabled_count": sum(1 for candidate in candidates if candidate.get("execution_enabled")),
            "provenance": "external-untrusted",
        },
        "promotion_blockers": promotion_blockers,
    }


def _parse_winapp2(text: str) -> list[_RawExternalRule]:
    parser = _CasePreservingConfigParser(interpolation=None, strict=False)
    parser.read_string(text)
    rules: list[_RawExternalRule] = []
    for section in parser.sections():
        title = section.strip()
        owner = title.rstrip("*").strip() or "external-winapp2"
        section_items = dict(parser.items(section))
        detection = {
            "detect": [value for key, value in section_items.items() if key.lower().startswith("detect") and not key.lower().startswith("detectos")],
            "detect_os": [value for key, value in section_items.items() if key.lower().startswith("detectos")],
            "special_detect": [value for key, value in section_items.items() if key.lower().startswith("specialdetect")],
        }
        exclusions = [
            {"key": key, "pattern": _normalise_path(value)}
            for key, value in section_items.items()
            if key.lower().startswith("excludekey")
        ]
        unsupported_section_semantics = [
            key
            for key in section_items
            if key.lower().startswith(("specialdetect", "warning", "detectos"))
        ]
        warning = next((value for key, value in section_items.items() if key.lower().startswith("warning")), "")
        section_metadata = {
            "section": section,
            "lang_sec_ref": section_items.get("LangSecRef", ""),
            "detect_count": len(detection["detect"]),
            "detect_os_count": len(detection["detect_os"]),
            "special_detect_count": len(detection["special_detect"]),
            "exclude_key_count": len(exclusions),
            "warning_present": bool(warning),
        }
        for key, value in parser.items(section):
            key_lower = key.lower()
            if not key_lower.startswith(("filekey", "regkey")):
                continue
            parts = [part.strip() for part in value.split("|")]
            pattern = "\\".join(part for part in parts[:2] if part) if key_lower.startswith("filekey") else value
            action_flags = parts[2:] if key_lower.startswith("filekey") else []
            unsupported_semantics = list(unsupported_section_semantics)
            unsupported_semantics.extend(flag for flag in action_flags if flag.upper() not in {"RECURSE", "REMOVESELF"})
            rules.append(
                _RawExternalRule(
                    rule_id=f"{section}.{key}",
                    title=title,
                    original_pattern=pattern,
                    owner=owner,
                    category_hint=f"{section} {key}",
                    action="filekey" if key_lower.startswith("filekey") else "regkey",
                    section_metadata={**section_metadata, "entry_key": key, "filekey_flags": action_flags},
                    detection=detection,
                    exclusions=exclusions,
                    unsupported_semantics=sorted(set(unsupported_semantics)),
                    warning=warning,
                )
            )
    return rules


def _cleanerml_child_texts(element: ET.Element, child_name: str) -> list[str]:
    values = []
    for child in element:
        if child.tag.lower().split("}")[-1] == child_name and child.text and child.text.strip():
            values.append(child.text.strip())
    return values


def _cleanerml_child_attrs(element: ET.Element, child_name: str) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for child in element.iter():
        if child is element:
            continue
        if child.tag.lower().split("}")[-1] == child_name:
            values.append({str(key): str(value) for key, value in child.attrib.items()})
    return values


def _parse_cleanerml(text: str) -> list[_RawExternalRule]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"failed to parse CleanerML XML: {exc}") from exc
    rules: list[_RawExternalRule] = []
    for cleaner in root.iter():
        if cleaner.tag.lower().split("}")[-1] != "cleaner":
            continue
        cleaner_id = cleaner.attrib.get("id") or cleaner.attrib.get("name") or "cleanerml-cleaner"
        label = cleaner.attrib.get("label") or cleaner_id
        category = cleaner.attrib.get("category") or cleaner.attrib.get("type") or ""
        for child in cleaner:
            if child.tag.lower().split("}")[-1] == "label" and child.text and child.text.strip():
                label = child.text.strip()
                break
        options = [
            {str(key): str(value) for key, value in option.attrib.items()}
            for option in cleaner.iter()
            if option.tag.lower().split("}")[-1] == "option"
        ]
        detect_attrs = _cleanerml_child_attrs(cleaner, "detect")
        detect_texts = _cleanerml_child_texts(cleaner, "detect")
        detection: dict[str, Any] = {
            "detect": detect_attrs,
            "detect_text": detect_texts,
        }
        exclusions = [
            {"key": exclude.attrib.get("id") or exclude.attrib.get("type") or "exclude", "pattern": _normalise_path(exclude.attrib.get("path") or exclude.attrib.get("regex") or exclude.text or "")}
            for exclude in cleaner.iter()
            if exclude.tag.lower().split("}")[-1] == "exclude"
        ]
        section_metadata = {
            "cleaner_id": cleaner_id,
            "category": category,
            "option_count": len(options),
            "detect_count": len(detect_attrs) + len(detect_texts),
            "exclude_count": len(exclusions),
            "options": options,
        }
        for action in cleaner.iter():
            if action.tag.lower().split("}")[-1] != "action":
                continue
            pattern = action.attrib.get("path") or action.attrib.get("regex") or action.attrib.get("search") or ""
            if not pattern:
                continue
            action_id = action.attrib.get("command") or action.attrib.get("id") or "action"
            unsupported_semantics = []
            if action.attrib.get("regex"):
                unsupported_semantics.append("action-regex")
            if action.attrib.get("search"):
                unsupported_semantics.append("action-search")
            if action_id.lower() not in {"delete", "deletefiles", "deletepath"}:
                unsupported_semantics.append(f"action-command:{action_id}")
            rules.append(
                _RawExternalRule(
                    rule_id=f"{cleaner_id}.{action_id}.{len(rules) + 1}",
                    title=label,
                    original_pattern=pattern,
                    owner=label,
                    category_hint=f"{cleaner_id} {category} {action_id}",
                    action=action_id,
                    section_metadata={**section_metadata, "action_attributes": {str(key): str(value) for key, value in action.attrib.items()}},
                    detection=detection,
                    exclusions=exclusions,
                    unsupported_semantics=sorted(set(unsupported_semantics)),
                )
            )
    return rules


def translate_external_rules_text(
    text: str,
    *,
    source_format: str = "auto",
    upstream_project: str | None = None,
    upstream_rule_id_or_commit: str = DEFAULT_UPSTREAM_COMMIT,
    license_name: str = DEFAULT_LICENSE,
    source_path: str | None = None,
) -> dict[str, Any]:
    resolved_format = _normalise_format(source_format, text)
    project = upstream_project or ("BleachBit/winapp2.ini" if resolved_format == "winapp2" else "BleachBit/CleanerML")
    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    import_batch_id = f"external-{resolved_format}-{source_hash[:12]}"
    source = ExternalRuleSource(
        source_format=resolved_format,
        upstream_project=project,
        upstream_rule_id_or_commit=upstream_rule_id_or_commit,
        license=license_name,
        source_hash=source_hash,
        import_batch_id=import_batch_id,
        source_path=source_path,
    )
    raw_rules = _parse_winapp2(text) if resolved_format == "winapp2" else _parse_cleanerml(text)
    candidates = [_candidate_from_raw(raw_rule, source) for raw_rule in raw_rules]
    import_sandbox = _import_sandbox(candidates, source)
    return {
        "schema": EXTERNAL_RULE_TRANSLATION_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "execution_enabled": False,
        "source": {
            "format": resolved_format,
            "path": source.source_path,
            "upstream_project": source.upstream_project,
            "upstream_rule_id_or_commit": source.upstream_rule_id_or_commit,
            "license": source.license,
            "source_hash": source.source_hash,
            "import_batch_id": source.import_batch_id,
        },
        "candidates": candidates,
        "import_sandbox": import_sandbox,
        "summary": {
            "candidate_count": len(candidates),
            "review_queue_count": import_sandbox["summary"]["review_queue_count"],
            "review_required_count": sum(1 for candidate in candidates if candidate["review_required"]),
            "dangerous_path_count": sum(1 for candidate in candidates if candidate["dangerous_path"]),
            "unsupported_semantic_count": sum(len(candidate.get("unsupported_semantics", [])) for candidate in candidates),
            "execution_enabled_count": sum(1 for candidate in candidates if candidate["execution_enabled"]),
            "owner_missing_count": import_sandbox["summary"]["owner_missing_count"],
            "rationale_missing_count": import_sandbox["summary"]["rationale_missing_count"],
            "provenance": "external-untrusted",
        },
        "promotion_gate": {
            "requires_schema_validation": True,
            "requires_owner_review": True,
            "requires_fixture_coverage": True,
            "requires_sensitive_exclusions": True,
            "requires_dangerous_path_scan": True,
            "requires_dry_run_evidence": True,
            "execution_enabled": False,
        },
        "non_goals": [
            "This translator does not download upstream cleaner catalogs.",
            "This translator does not execute external cleaner rules.",
            "This translator does not promote translated candidates into builtin cleanup rules.",
        ],
    }


def translate_external_rules_file(
    path: Path,
    *,
    source_format: str = "auto",
    upstream_project: str | None = None,
    upstream_rule_id_or_commit: str = DEFAULT_UPSTREAM_COMMIT,
    license_name: str = DEFAULT_LICENSE,
) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return translate_external_rules_text(
        text,
        source_format=source_format,
        upstream_project=upstream_project,
        upstream_rule_id_or_commit=upstream_rule_id_or_commit,
        license_name=license_name,
        source_path=str(path),
    )


def external_rule_translation_sample() -> dict[str, Any]:
    sample = """
[Example Browser Cache *]
LangSecRef=3029
DetectFile=%LocalAppData%\\ExampleBrowser\\User Data\\Default
FileKey1=%LocalAppData%\\ExampleBrowser\\User Data\\Default\\Cache|*.*|RECURSE
FileKey2=%UserProfile%\\Documents|*.*|RECURSE
""".strip()
    return translate_external_rules_text(
        sample,
        source_format="winapp2",
        upstream_project="BleachBit/winapp2.ini",
        upstream_rule_id_or_commit="sample",
        license_name="GPL-3.0-or-later-or-upstream-license-review",
        source_path=None,
    )
