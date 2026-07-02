"""CleanWin JSON models."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN_SCHEMA = "cleanwin.plan.v1"

CATEGORY_TEMP = "temp"
CATEGORY_DEV_CACHE = "dev-cache"
CATEGORY_PACKAGE_CACHE = "package-cache"
CATEGORY_BROWSER_CACHE = "browser-cache"
CATEGORY_APP_LEFTOVERS = "app-leftovers"

ALL_CATEGORIES: tuple[str, ...] = (
    CATEGORY_TEMP,
    CATEGORY_DEV_CACHE,
    CATEGORY_PACKAGE_CACHE,
    CATEGORY_BROWSER_CACHE,
    CATEGORY_APP_LEFTOVERS,
)

EXECUTABLE_CACHE_CATEGORIES = frozenset({CATEGORY_TEMP, CATEGORY_DEV_CACHE, CATEGORY_PACKAGE_CACHE, CATEGORY_BROWSER_CACHE})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class HostContext:
    hostname: str
    platform: str
    os_name: str
    user: str
    home: str

    @classmethod
    def current(cls) -> HostContext:
        return cls(
            hostname=socket.gethostname(),
            platform=platform.platform(),
            os_name=os.name,
            user=os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
            home=str(Path.home()),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "hostname": self.hostname,
            "platform": self.platform,
            "os_name": self.os_name,
            "user": self.user,
            "home": self.home,
        }


@dataclass(frozen=True)
class Candidate:
    path: str
    category: str
    size_bytes: int
    reason: str
    safe_to_delete: bool
    delete_mode: str = "recycle"
    requires_admin: bool = False
    risk: str = "low"
    discovered_by: str = "collector"
    modified_at: str | None = None
    identity: dict[str, Any] | None = None
    rule_id: str | None = None
    cache_owner: str | None = None
    official_cleanup_command: str | None = None
    safe_to_delete_rationale: str | None = None
    cache_layer: str | None = None
    cache_layer_family: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "category": self.category,
            "size_bytes": self.size_bytes,
            "reason": self.reason,
            "safe_to_delete": self.safe_to_delete,
            "delete_mode": self.delete_mode,
            "requires_admin": self.requires_admin,
            "risk": self.risk,
            "discovered_by": self.discovered_by,
            "modified_at": self.modified_at,
            "identity": self.identity,
            "rule_id": self.rule_id,
            "cache_owner": self.cache_owner,
            "official_cleanup_command": self.official_cleanup_command,
            "safe_to_delete_rationale": self.safe_to_delete_rationale,
            "cache_layer": self.cache_layer,
            "cache_layer_family": self.cache_layer_family,
        }


@dataclass(frozen=True)
class Finding:
    category: str
    title: str
    detail: str
    risk: str
    safe_to_execute: bool = False
    rule_id: str | None = None
    owner: str | None = None
    official_cleanup_command: str | None = None
    review_details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "title": self.title,
            "detail": self.detail,
            "risk": self.risk,
            "safe_to_execute": self.safe_to_execute,
            "rule_id": self.rule_id,
            "owner": self.owner,
            "official_cleanup_command": self.official_cleanup_command,
            "review_details": self.review_details,
        }


@dataclass(frozen=True)
class Plan:
    candidates: list[Candidate]
    categories: list[str]
    context: HostContext = field(default_factory=HostContext.current)
    created_at: str = field(default_factory=utc_now)
    schema: str = PLAN_SCHEMA

    def source_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "categories": self.categories,
            "context": self.context.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }

    def source_fingerprint(self) -> str:
        return hashlib.sha256(stable_json(self.source_payload()).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = self.source_payload()
        payload["created_at"] = self.created_at
        payload["source_fingerprint"] = self.source_fingerprint()
        payload["summary"] = {
            "candidate_count": len(self.candidates),
            "safe_candidate_count": sum(1 for candidate in self.candidates if candidate.safe_to_delete),
            "bytes_reclaimable": sum(candidate.size_bytes for candidate in self.candidates if candidate.safe_to_delete),
        }
        return payload


def candidate_from_dict(value: dict[str, Any]) -> Candidate:
    return Candidate(
        path=str(value["path"]),
        category=str(value["category"]),
        size_bytes=int(value.get("size_bytes", 0)),
        reason=str(value.get("reason", "")),
        safe_to_delete=bool(value.get("safe_to_delete", False)),
        delete_mode=str(value.get("delete_mode", "recycle")),
        requires_admin=bool(value.get("requires_admin", False)),
        risk=str(value.get("risk", "low")),
        discovered_by=str(value.get("discovered_by", "collector")),
        modified_at=value.get("modified_at"),
        identity=value.get("identity") if isinstance(value.get("identity"), dict) else None,
        rule_id=value.get("rule_id"),
        cache_owner=value.get("cache_owner"),
        official_cleanup_command=value.get("official_cleanup_command"),
        safe_to_delete_rationale=value.get("safe_to_delete_rationale"),
        cache_layer=value.get("cache_layer"),
        cache_layer_family=value.get("cache_layer_family"),
    )


def plan_from_dict(value: dict[str, Any]) -> Plan:
    context_raw = value.get("context", {})
    context = HostContext(
        hostname=str(context_raw.get("hostname", "")),
        platform=str(context_raw.get("platform", "")),
        os_name=str(context_raw.get("os_name", "")),
        user=str(context_raw.get("user", "")),
        home=str(context_raw.get("home", "")),
    )
    return Plan(
        candidates=[candidate_from_dict(item) for item in value.get("candidates", [])],
        categories=[str(item) for item in value.get("categories", [])],
        context=context,
        created_at=str(value.get("created_at", utc_now())),
        schema=str(value.get("schema", PLAN_SCHEMA)),
    )
