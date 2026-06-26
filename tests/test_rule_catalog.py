from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

import pytest

from cleanwincli.rule_catalog import CATALOG_SCHEMA, RuleCatalogError, cleanup_rule_catalog

JSONPayload = dict[str, Any]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertContainsNone = Callable[[Collection[Any], Sequence[Any]], None]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]
AssertUniqueItems = Callable[[Sequence[Any]], Sequence[Any]]
AssertNonEmpty = Callable[[Sequence[Any]], Sequence[Any]]
AssertAtLeast = Callable[[int, int], int]
AssertTextContainsAny = Callable[[str, Sequence[str]], str]


@pytest.fixture
def rule_catalog() -> dict[str, Any]:
    return cleanup_rule_catalog()


def catalog_rules(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *catalog["dev_cache_rules"],
        *catalog["package_cache_rules"],
        *catalog["browser_cache_rules"],
        *catalog["app_leftover_rules"],
        *catalog["browser_profile_cache_rules"].values(),
    ]


def test_cleanup_rule_catalog_loads_versioned_rules(
    rule_catalog: dict[str, Any],
    assert_payload_schema: AssertPayloadSchema,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
    assert_at_least: AssertAtLeast,
) -> None:
    catalog = rule_catalog

    assert_payload_schema(catalog, CATALOG_SCHEMA)
    assert_field_values(catalog, {"version": "1"})
    assert_at_least(catalog["rule_count"], 40)
    assert_contains_all(
        {rule["rule_id"] for rule in catalog["dev_cache_rules"]},
        ["dev-cache.npm.cache", "dev-cache.poetry.cache"],
    )
    assert_contains_all(
        {rule["rule_id"] for rule in catalog["app_leftover_rules"]},
        ["app-leftovers.vscode.cached-data"],
    )


@pytest.mark.parametrize(
    "rule_id",
    [
        "dev-cache.poetry.cache",
        "dev-cache.pipenv.cache",
        "dev-cache.pre-commit.cache",
        "dev-cache.node-gyp.cache",
        "app-leftovers.teams-classic.gpu-cache",
        "app-leftovers.discord.gpu-cache",
        "app-leftovers.vscode.gpu-cache",
        "app-leftovers.telegram.cache",
        "app-leftovers.cursor.cached-data",
        "app-leftovers.android-studio.logs",
        "app-leftovers.virtualbox.logs",
        "app-leftovers.vlc.art-cache",
        "app-leftovers.1password.logs",
        "app-leftovers.github-desktop.gpu-cache",
        "app-leftovers.obsidian.gpu-cache",
        "app-leftovers.unity-hub.logs",
        "app-leftovers.unreal-engine-launcher.webcache",
        "app-leftovers.ea-app.cache",
        "app-leftovers.gog-galaxy.webcache",
        "app-leftovers.ubisoft-connect.cache",
        "app-leftovers.dropbox.logs",
        "app-leftovers.logitech-g-hub.logs",
        "app-leftovers.razer-synapse.logs",
        "app-leftovers.skype.media-cache",
        "app-leftovers.webex.logs",
        "app-leftovers.msteams-new.logs",
        "app-leftovers.todoist.gpu-cache",
        "app-leftovers.linear.gpu-cache",
        "app-leftovers.canva.gpu-cache",
        "app-leftovers.powershell.startup-cache",
        "app-leftovers.windows-terminal.state-cache",
        "app-leftovers.snagit.logs",
        "app-leftovers.camtasia.logs",
        "app-leftovers.parsec.logs",
        "app-leftovers.anydesk.logs",
        "app-leftovers.teamviewer.logs",
        "app-leftovers.vpn-openvpn.logs",
        "app-leftovers.warp.logs",
        "app-leftovers.wireshark.recent-cache",
        "app-leftovers.filezilla.logs",
        "app-leftovers.winscp.logs",
        "app-leftovers.calibre.cache",
        "app-leftovers.qbittorrent.logs",
        "app-leftovers.dbeaver.logs",
        "app-leftovers.datagrip.logs",
        "app-leftovers.mysql-workbench.logs",
        "app-leftovers.azure-data-studio.cached-data",
        "app-leftovers.insomnia.gpu-cache",
        "app-leftovers.bruno.logs",
        "app-leftovers.tableau.logs",
        "app-leftovers.autodesk.logs",
        "app-leftovers.blender.cache",
        "app-leftovers.hp-smart.logs",
        "app-leftovers.powertoys.logs",
        "app-leftovers.onedrive.logs",
        "app-leftovers.google-drivefs.logs",
        "app-leftovers.icloud.logs",
        "app-leftovers.gimp.thumbnails",
        "app-leftovers.inkscape.cache",
        "app-leftovers.krita.cache",
        "app-leftovers.audacity.logs",
        "app-leftovers.handbrake.logs",
        "app-leftovers.corsair-icue.logs",
        "app-leftovers.sourcetree.logs",
        "app-leftovers.gitkraken.gpu-cache",
        "app-leftovers.tortoisegit.crashdumps",
        "app-leftovers.fork.logs",
        "app-leftovers.lens.gpu-cache",
        "app-leftovers.rancher-desktop.logs",
        "app-leftovers.podman-desktop.gpu-cache",
        "app-leftovers.heidisql.logs",
        "app-leftovers.ssms.logs",
        "app-leftovers.typora.gpu-cache",
        "app-leftovers.dell-supportassist.logs",
        "app-leftovers.lenovo-vantage.logs",
        "app-leftovers.armoury-crate.logs",
        "app-leftovers.msi-center.logs",
        "app-leftovers.steelseries-gg.logs",
        "app-leftovers.elgato.logs",
        "app-leftovers.stream-deck.logs",
        "app-leftovers.gopro-player.gpu-cache",
        "app-leftovers.garmin-express.logs",
        "app-leftovers.wacom-tablet.logs",
        "app-leftovers.box-drive.logs",
        "app-leftovers.mega.logs",
        "app-leftovers.joplin.gpu-cache",
        "app-leftovers.standard-notes.gpu-cache",
        "app-leftovers.simplenote.gpu-cache",
        "app-leftovers.sharex.logs",
        "app-leftovers.greenshot.logs",
        "app-leftovers.lightshot.logs",
        "app-leftovers.screentogif.logs",
        "app-leftovers.naps2.logs",
        "app-leftovers.backblaze.logs",
        "app-leftovers.acronis.logs",
        "app-leftovers.macrium.logs",
        "app-leftovers.freefilesync.logs",
        "app-leftovers.everything.crashdumps",
        "app-leftovers.keepassxc.crashdumps",
        "app-leftovers.sumatrapdf.crashdumps",
        "app-leftovers.foxit.logs",
        "app-leftovers.viber.gpu-cache",
        "app-leftovers.element.gpu-cache",
    ],
)
def test_cleanup_rule_catalog_regenerated_rules_have_reviewable_rationale(
    rule_id: str,
    rule_catalog: dict[str, Any],
    assert_non_empty: AssertNonEmpty,
    assert_text_contains_any: AssertTextContainsAny,
) -> None:
    rule = {rule["rule_id"]: rule for rule in catalog_rules(rule_catalog)}[rule_id]
    assert_non_empty([rule["official_cleanup_command"]])
    assert_text_contains_any(rule["rationale"].lower(), ["regenerated", "recreated"])


def test_cleanup_rule_catalog_expanded_rules_avoid_unsafe_default_segments(
    rule_catalog: dict[str, Any],
    assert_contains_none: AssertContainsNone,
) -> None:
    rules = catalog_rules(rule_catalog)
    unsafe_segments = {"documents", "desktop", "cookies", "login data", "sessions", "extensions", "history"}
    for rule in rules:
        default_segments = {segment.strip().lower() for segment in str(rule.get("default", "")).replace("\\", "/").split("/")}
        assert_contains_none(default_segments, sorted(unsafe_segments))


def test_cleanup_rule_catalog_rule_ids_are_unique(
    rule_catalog: dict[str, Any], assert_unique_items: AssertUniqueItems
) -> None:
    catalog = rule_catalog
    rule_ids: list[str] = []
    for section in ("dev_cache_rules", "package_cache_rules", "browser_cache_rules", "app_leftover_rules"):
        rule_ids.extend(rule["rule_id"] for rule in catalog[section])
    rule_ids.extend(rule["rule_id"] for rule in catalog["browser_profile_cache_rules"].values())

    assert_unique_items(rule_ids)


def test_cleanup_rule_catalog_rejects_duplicate_rule_ids() -> None:
    from cleanwincli.rule_catalog import _validate_catalog

    payload = {
        "schema": CATALOG_SCHEMA,
        "version": "1",
        "dev_cache_rules": [
            {
                "rule_id": "duplicate.rule",
                "owner": "one",
                "env_key": "ONE_CACHE",
                "default": "local:one",
                "official_cleanup_command": "one clean",
                "rationale": "one",
            }
        ],
        "package_cache_rules": [
            {
                "rule_id": "duplicate.rule",
                "owner": "two",
                "default": "local:two",
                "official_cleanup_command": "two clean",
                "rationale": "two",
            }
        ],
        "browser_cache_rules": [],
        "browser_profile_cache_rules": {},
        "app_leftover_rules": [],
    }

    with pytest.raises(RuleCatalogError, match="duplicate cleanup rule_id"):
        _validate_catalog(payload)
