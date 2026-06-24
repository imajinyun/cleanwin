"""Read-only cleanup preset catalog."""

from __future__ import annotations

from typing import Any

PRESET_CATALOG_SCHEMA = "cleanwin.preset-catalog.v1"


def _preset(
    preset_id: str,
    *,
    title: str,
    categories: list[str],
    rule_ids: list[str],
    risk: str,
    target_user: str,
    review_steps: list[str],
) -> dict[str, Any]:
    argv = ["cleanwin", "--json", "plan", "--categories", ",".join(categories)]
    for rule_id in rule_ids:
        argv.extend(["--rule-id", rule_id])
    return {
        "id": preset_id,
        "title": title,
        "categories": categories,
        "rule_ids": rule_ids,
        "risk": risk,
        "target_user": target_user,
        "plan_template": {
            "schema": "cleanwin.preset-plan-template.v1",
            "argv": argv,
            "destructive": False,
            "execution_enabled": False,
            "requires_plan_review": True,
            "requires_validate_plan": True,
            "requires_matching_dry_run_token": True,
        },
        "review_steps": review_steps,
    }


def preset_catalog_report() -> dict[str, Any]:
    presets = [
        _preset(
            "preset.daily-safe-cache",
            title="Daily safe cache review",
            categories=["temp", "dev-cache", "package-cache"],
            rule_ids=[
                "dev-cache.npm.cache",
                "dev-cache.pip.cache",
                "dev-cache.go-build.cache",
                "package-cache.winget.packages",
                "package-cache.uv.cache",
            ],
            risk="low",
            target_user="general-developer",
            review_steps=["Review candidate paths before execution.", "Prefer official cleanup commands where available."],
        ),
        _preset(
            "preset.browser-cache-only",
            title="Browser cache only",
            categories=["browser-cache"],
            rule_ids=[
                "browser-cache.chrome.cache",
                "browser-cache.chrome.code-cache",
                "browser-cache.edge.cache",
                "browser-cache.edge.code-cache",
                "browser-cache.firefox.cache2",
                "browser-cache.brave.cache",
                "browser-cache.brave.code-cache",
            ],
            risk="medium",
            target_user="browser-heavy-user",
            review_steps=["Confirm browser profiles are not locked.", "Exclude cookies, passwords, sessions, extensions, history, and profile databases."],
        ),
        _preset(
            "preset.uninstalled-app-leftovers",
            title="Uninstalled app leftover review",
            categories=["app-leftovers"],
            rule_ids=[
                "app-leftovers.slack.cache",
                "app-leftovers.teams-classic.logs",
                "app-leftovers.discord.cache",
                "app-leftovers.vscode.cached-data",
                "app-leftovers.postman.cache",
            ],
            risk="medium",
            target_user="app-cleanup-review",
            review_steps=["Check installed-app-inventory before planning leftovers.", "Skip cleanup when active install markers are present."],
        ),
    ]
    return {
        "schema": PRESET_CATALOG_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "presets": presets,
        "summary": {
            "preset_count": len(presets),
            "execution_enabled_count": sum(1 for preset in presets if preset["plan_template"]["execution_enabled"]),
            "rule_id_count": len({rule_id for preset in presets for rule_id in preset["rule_ids"]}),
        },
        "execution_gate": {
            "preset_execution_enabled": False,
            "requires_explicit_plan_generation": True,
            "requires_validate_plan": True,
            "requires_human_review": True,
            "requires_matching_dry_run_token": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not execute presets.",
            "This report does not bypass plan validation, review, or dry-run token confirmation.",
        ],
    }
