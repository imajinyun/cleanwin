from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

import pytest

from cleanwincli.rule_catalog import (
    CATALOG_SCHEMA,
    RULE_PACK_CATALOG_SCHEMA,
    RULE_PACK_SCHEMA,
    RULE_QUALITY_DASHBOARD_SCHEMA,
    RULE_QUALITY_SCORE_SCHEMA,
    RuleCatalogError,
    cleanup_rule_catalog,
    rule_pack_catalog_report,
    rule_quality_dashboard_report,
)

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
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertSchemaSamples = Callable[[Sequence[str]], dict[str, JSONPayload]]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]


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
    assert_field_values(catalog, {"rule_pack_count": 5})
    assert_contains_all(
        {pack["pack_id"] for pack in catalog["rule_packs"]},
        ["app-leftovers", "browser-cache", "browser-profile-cache", "dev-cache", "package-cache"],
    )


def test_cleanup_rule_catalog_enriches_rules_with_quality_scores(
    rule_catalog: dict[str, Any],
    assert_payload_schema: AssertPayloadSchema,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    rule = {rule["rule_id"]: rule for rule in catalog_rules(rule_catalog)}["app-leftovers.vscode.cached-data"]

    assert_field_values(rule, {"schema": "cleanwin.cleanup-rule.v1", "rule_pack": "app-leftovers"})
    quality = assert_payload_schema(rule["quality_score"], RULE_QUALITY_SCORE_SCHEMA)
    assert_field_values(
        quality,
        {
            "risk": "medium",
            "recoverability": "high",
            "owner_evidence": True,
            "official_cleanup_evidence": True,
            "rationale_evidence": True,
            "provenance": "builtin",
            "review_status": "manual-reviewed",
        },
    )
    assert quality["score"] >= 80
    assert_contains_all(quality.keys(), ["active_install_marker_count", "sensitive_exclusion_matches", "test_coverage"])


@pytest.mark.parametrize(
    ("rule_id", "cache_layer", "cache_layer_family"),
    [
        ("dev-cache.go-build.cache", "build-cache", "build-cache"),
        ("dev-cache.npm.cache", "dependency-cache", "dependency-cache"),
        ("dev-cache.jetbrains.index-cache", "index-cache", "metadata-cache"),
        ("package-cache.winget.packages", "package-download-cache", "package-cache"),
        ("package-cache.chocolatey.lib-bad", "package-install-cache", "package-cache"),
        ("package-cache.visual-studio.installer-cache", "package-install-cache", "package-cache"),
        ("browser-cache.chrome.cache", "http-cache", "browser-cache"),
        ("browser-cache.chrome.code-cache", "code-cache", "browser-cache"),
        ("browser-cache.chrome.gpu-cache", "gpu-cache", "renderer-cache"),
        ("browser-cache.chrome.service-worker-cache", "service-worker-cache", "browser-cache"),
        ("browser-cache.firefox.startup-cache", "startup-cache", "runtime-cache"),
        ("app-leftovers.vscode.gpu-cache", "gpu-cache", "renderer-cache"),
        ("app-leftovers.tortoisegit.crashdumps", "crash-dumps", "diagnostics"),
    ],
)
def test_cleanup_rule_catalog_enriches_cache_layer_taxonomy(
    rule_catalog: dict[str, Any],
    rule_id: str,
    cache_layer: str,
    cache_layer_family: str,
    assert_field_values: AssertFieldValues,
) -> None:
    rule = {rule["rule_id"]: rule for rule in catalog_rules(rule_catalog)}[rule_id]

    assert_field_values(rule, {"cache_layer": cache_layer, "cache_layer_family": cache_layer_family})


def test_rule_pack_catalog_report_is_readonly_and_summarizes_builtin_packs(
    assert_readonly_report: AssertReadonlyReport,
    assert_payload_schema: AssertPayloadSchema,
    assert_exact_set: Callable[[Collection[Any], Collection[Any]], set[Any]],
    assert_field_values: AssertFieldValues,
) -> None:
    report = assert_readonly_report(rule_pack_catalog_report(), RULE_PACK_CATALOG_SCHEMA)

    assert_field_values(
        report,
        {
            "summary.pack_count": 5,
            "summary.builtin_pack_count": 5,
            "summary.manual_reviewed_pack_count": 5,
            "summary.execution_enabled_count": 0,
            "promotion_gate.external_rule_import_enabled": False,
            "promotion_gate.requires_quality_score": True,
        },
    )
    assert_exact_set(
        [pack["pack_id"] for pack in report["packs"]],
        {"app-leftovers", "browser-cache", "browser-profile-cache", "dev-cache", "package-cache"},
    )
    for pack in report["packs"]:
        assert_payload_schema(pack, RULE_PACK_SCHEMA)
        assert pack["source"] == "builtin"
        assert pack["review_status"] == "manual-reviewed"
        assert pack["rule_count"] == len(pack["rule_ids"])
        assert pack["quality"]["minimum_score"] > 0
        assert pack["cache_layers"]
        assert pack["cache_layer_families"]


def test_rule_pack_catalog_exposes_versioned_external_import_sandbox(
    assert_field_values: AssertFieldValues,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = rule_pack_catalog_report()

    assert_field_values(
        report,
        {
            "versioning.rule_pack_schema": RULE_PACK_SCHEMA,
            "versioning.rule_schema": "cleanwin.cleanup-rule.v1",
            "versioning.quality_schema": RULE_QUALITY_SCORE_SCHEMA,
            "external_import_sandbox.schema": "cleanwin.external-rule-import-sandbox.v1",
            "external_import_sandbox.default_import_mode": "report-only",
            "external_import_sandbox.execution_enabled": False,
            "external_import_sandbox.allowed_sources.0": "local-file",
            "external_import_sandbox.supported_formats.0": "winapp2",
            "external_import_sandbox.supported_formats.1": "cleanerml",
        },
    )
    assert_contains_all(
        report["external_import_sandbox"]["required_review_fields"],
        ["import_batch_id", "source_hash", "owner", "reviewer", "rationale", "sensitive_exclusions", "fixture_coverage", "quality_score"],
    )
    assert_contains_all(
        report["external_import_sandbox"]["promotion_blockers"],
        ["external-untrusted-provenance", "execution-disabled-by-default", "schema-validation-required", "unsupported-semantics-review-required"],
    )
    assert_contains_all(
        report["external_import_sandbox"]["provenance_index"]["tracked_provenance"],
        ["builtin", "translated-winapp2", "translated-cleanerml", "manual-reviewed", "external-untrusted"],
    )
    assert_contains_all(
        report["external_import_sandbox"]["review_queue_contract"]["required_fields"],
        ["import_batch_id", "source_hash", "external_rule_id", "translated_rule_id", "promotion_blockers"],
    )


def test_rule_quality_dashboard_is_readonly_and_summarizes_rule_health(
    assert_readonly_report: AssertReadonlyReport,
    assert_field_values: AssertFieldValues,
    assert_contains_all: AssertContainsAll,
    assert_at_least: AssertAtLeast,
) -> None:
    dashboard = assert_readonly_report(rule_quality_dashboard_report(), RULE_QUALITY_DASHBOARD_SCHEMA)

    assert_field_values(
        dashboard,
        {
            "quality_schema": RULE_QUALITY_SCORE_SCHEMA,
            "summary.pack_count": 5,
            "summary.execution_enabled_count": 0,
            "promotion_gate.requires_quality_score": True,
            "promotion_gate.execution_enabled": False,
        },
    )
    assert_at_least(dashboard["summary"]["rule_count"], 40)
    assert_at_least(dashboard["summary"]["minimum_score"], 60)
    assert_contains_all(dashboard["risk_counts"], ["low", "medium", "high"])
    assert_contains_all(dashboard["recoverability_counts"], ["high", "medium", "low"])
    assert_contains_all(dashboard["cache_layer_counts"], ["http-cache", "code-cache", "gpu-cache", "package-download-cache"])
    assert_contains_all(dashboard["cache_layer_family_counts"], ["browser-cache", "package-cache", "renderer-cache", "diagnostics"])
    assert_contains_all(dashboard["quality_buckets"], ["excellent", "good", "review", "blocked"])
    assert_contains_all(
        dashboard["evidence_gap_counts"],
        [
            "missing_owner",
            "missing_official_cleanup_command",
            "missing_rationale",
            "missing_active_install_marker",
            "sensitive_exclusion_match",
        ],
    )
    assert {pack["pack_id"] for pack in dashboard["packs"]} == {
        "app-leftovers",
        "browser-cache",
        "browser-profile-cache",
        "dev-cache",
        "package-cache",
    }


def test_rule_pack_catalog_is_exposed_by_cli_provider_and_schema_registry(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_schema_samples: AssertSchemaSamples,
    assert_payload_schema: AssertPayloadSchema,
    assert_summary_counts: AssertSummaryCounts,
) -> None:
    sample = assert_cli_provider_schema_sample("rule-pack-catalog", RULE_PACK_CATALOG_SCHEMA)

    assert_summary_counts(sample, {"pack_count": 5})
    dashboard = assert_cli_provider_schema_sample("rule-quality-dashboard", RULE_QUALITY_DASHBOARD_SCHEMA)
    assert_summary_counts(dashboard, {"pack_count": 5})
    samples = assert_schema_samples([RULE_PACK_SCHEMA, RULE_QUALITY_SCORE_SCHEMA, RULE_QUALITY_DASHBOARD_SCHEMA])
    assert_payload_schema(samples[RULE_PACK_SCHEMA], RULE_PACK_SCHEMA)
    assert_payload_schema(samples[RULE_QUALITY_SCORE_SCHEMA], RULE_QUALITY_SCORE_SCHEMA)
    assert_payload_schema(samples[RULE_QUALITY_DASHBOARD_SCHEMA], RULE_QUALITY_DASHBOARD_SCHEMA)


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
        "app-leftovers.thunderbird.crashdumps",
        "app-leftovers.mailbird.logs",
        "app-leftovers.em-client.logs",
        "app-leftovers.zotero.logs",
        "app-leftovers.mendeley.logs",
        "app-leftovers.davinci-resolve.logs",
        "app-leftovers.shotcut.logs",
        "app-leftovers.kdenlive.cache",
        "app-leftovers.malwarebytes.logs",
        "app-leftovers.nordvpn.logs",
        "app-leftovers.plex.logs",
        "app-leftovers.jellyfin.logs",
        "app-leftovers.itunes.logs",
        "app-leftovers.kindle.logs",
        "app-leftovers.audible.logs",
        "app-leftovers.ringcentral.logs",
        "app-leftovers.bluejeans.logs",
        "app-leftovers.bitwarden.gpu-cache",
        "app-leftovers.protonvpn.logs",
        "app-leftovers.mullvad-vpn.logs",
        "app-leftovers.ccleaner.logs",
        "app-leftovers.revo-uninstaller.logs",
        "app-leftovers.bleachbit.logs",
        "app-leftovers.windirstat.ini",
        "app-leftovers.wiztree.logs",
        "app-leftovers.treesize-free.logs",
        "app-leftovers.hwinfo.logs",
        "app-leftovers.cpu-z.logs",
        "app-leftovers.gpu-z.logs",
        "app-leftovers.irfanview.thumbnails",
        "app-leftovers.paintdotnet.crashdumps",
        "app-leftovers.xnviewmp.thumbnails",
        "app-leftovers.nomacs.cache",
        "app-leftovers.faststone.thumbnails",
        "app-leftovers.foobar2000.logs",
        "app-leftovers.aimp.logs",
        "app-leftovers.mpv.cache",
        "app-leftovers.mpc-hc.logs",
        "app-leftovers.potplayer.logs",
        "app-leftovers.notepad-plus-plus.backups",
        "app-leftovers.sublime-text.cache",
        "app-leftovers.7zip.crashdumps",
        "app-leftovers.winrar.crashdumps",
        "app-leftovers.peazip.crashdumps",
        "app-leftovers.bandizip.crashdumps",
        "app-leftovers.nanazip.crashdumps",
        "app-leftovers.rufus.crashdumps",
        "app-leftovers.balenaetcher.logs",
        "app-leftovers.raspberry-pi-imager.logs",
        "app-leftovers.ventoy.crashdumps",
        "app-leftovers.win32diskimager.crashdumps",
        "app-leftovers.putty.crashdumps",
        "app-leftovers.superputty.logs",
        "app-leftovers.mremoteng.logs",
        "app-leftovers.termius.logs",
        "app-leftovers.mobaxterm.logs",
        "app-leftovers.royal-ts.logs",
        "app-leftovers.bitvise-ssh-client.logs",
        "app-leftovers.cygwin-setup.logs",
        "app-leftovers.msys2-setup.logs",
        "app-leftovers.alacritty.crashdumps",
        "app-leftovers.streamlabs.logs",
        "app-leftovers.xsplit.logs",
        "app-leftovers.bandicam.logs",
        "app-leftovers.mirillis-action.logs",
        "app-leftovers.reaper.logs",
        "app-leftovers.fl-studio.logs",
        "app-leftovers.ableton-live.crashdumps",
        "app-leftovers.steinberg-cubase.logs",
        "app-leftovers.voicemeeter.logs",
        "app-leftovers.voicemod.logs",
        "app-leftovers.ultimaker-cura.logs",
        "app-leftovers.prusaslicer.logs",
        "app-leftovers.bambu-studio.logs",
        "app-leftovers.orca-slicer.logs",
        "app-leftovers.chitubox.logs",
        "app-leftovers.lychee-slicer.logs",
        "app-leftovers.freecad.crashdumps",
        "app-leftovers.openscad.logs",
        "app-leftovers.fusion360.logs",
        "app-leftovers.solidworks.crashdumps",
        "app-leftovers.vmware-workstation.logs",
        "app-leftovers.vmware-player.logs",
        "app-leftovers.genymotion.logs",
        "app-leftovers.bluestacks.logs",
        "app-leftovers.noxplayer.logs",
        "app-leftovers.ldplayer.logs",
        "app-leftovers.ollama.logs",
        "app-leftovers.lm-studio.logs",
        "app-leftovers.jan.logs",
        "app-leftovers.gpt4all.logs",
        "app-leftovers.pinokio.cache",
        "app-leftovers.fiddler-everywhere.logs",
        "app-leftovers.charles.logs",
        "app-leftovers.rustdesk.logs",
        "app-leftovers.tailscale.logs",
        "app-leftovers.zerotier.logs",
        "app-leftovers.moonlight.logs",
        "app-leftovers.sunshine.logs",
        "app-leftovers.visual-studio.logs",
        "app-leftovers.git-extensions.logs",
        "app-leftovers.gitahead.logs",
        "app-leftovers.mongodb-compass.gpu-cache",
        "app-leftovers.redisinsight.gpu-cache",
        "app-leftovers.nextcloud.logs",
        "app-leftovers.owncloud.logs",
        "app-leftovers.pcloud.logs",
        "app-leftovers.syncthing.logs",
        "app-leftovers.resilio-sync.logs",
        "app-leftovers.goodsync.logs",
        "app-leftovers.duplicati.logs",
        "app-leftovers.kopiaui.logs",
        "app-leftovers.cyberduck.logs",
        "app-leftovers.mountain-duck.logs",
        "app-leftovers.teracopy.logs",
        "app-leftovers.rclone-browser.logs",
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
