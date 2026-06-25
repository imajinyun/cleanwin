from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

import pytest

ROOT = Path(__file__).resolve().parents[1]
JSONPayload = dict[str, Any]
CommandSequence = Sequence[str | Sequence[str]]
SchemaPairs = Sequence[tuple[str, str]]
RunCleanWin = Callable[..., subprocess.CompletedProcess[str]]
CleanWinResultJSON = Callable[[subprocess.CompletedProcess[str]], JSONPayload]
CleanWinJSON = Callable[..., JSONPayload]
CleanWinPlanFile = Callable[..., JSONPayload]
CleanWinTestEnv = Callable[..., dict[str, str]]
WriteTextFile = Callable[[Path, str], Path]
WriteBytesFile = Callable[[Path, bytes], Path]
MakeDirectory = Callable[[Path], Path]
MakeWindowsCacheEnv = Callable[[Path], dict[str, str]]
AssertPlanFileValid = Callable[[Path, dict[str, str]], JSONPayload]
AssertDryRunResult = Callable[[JSONPayload, Path], JSONPayload]
ReadJSONFile = Callable[[Path], JSONPayload]
ReadJSONLRecord = Callable[[Path], JSONPayload]
WriteJSONFile = Callable[[Path, JSONPayload], Path]
TempPlanFixture = tuple[Path, Path, dict[str, str]]
MakeTempPlan = Callable[[Path, bool], TempPlanFixture]
AssertCliProviderSchema = Callable[[str, str], None]
AssertCliProviderSchemas = Callable[[SchemaPairs], None]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertCliProviderSchemaWithEnv = Callable[[str, str, dict[str, str]], None]
AssertAIProviderSchema = Callable[[str, str], None]
AssertAIProviderSchemaWithEnv = Callable[[str, str, dict[str, str]], None]
AssertAIProviderSchemas = Callable[[SchemaPairs], None]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertSchemasRegistered = Callable[[list[str]], None]
AssertSchemaSample = Callable[[str], JSONPayload]
AssertSchemaSamples = Callable[[Sequence[str]], dict[str, JSONPayload]]
AssertReadonlySchemaSample = Callable[[str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertSafeToExecuteDisabled = Callable[[JSONPayload], JSONPayload]
AssertCommandSequence = Callable[[CommandSequence, CommandSequence], None]


class AssertExecutionDisabled(Protocol):
    def __call__(self, payload: JSONPayload, *fields: str) -> JSONPayload: ...


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def cleanwin_test_env(repo_root: Path) -> CleanWinTestEnv:
    def _cleanwin_test_env(*, test_mode: bool = True, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo_root)
        if test_mode:
            env["CLEANWIN_TEST_MODE"] = "1"
        if extra:
            env.update(extra)
        return env

    return _cleanwin_test_env


@pytest.fixture
def write_text_file() -> WriteTextFile:
    def _write_text_file(path: Path, text: str = "x") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _write_text_file


@pytest.fixture
def write_bytes_file() -> WriteBytesFile:
    def _write_bytes_file(path: Path, contents: bytes = b"x") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        return path

    return _write_bytes_file


@pytest.fixture
def make_directory() -> MakeDirectory:
    def _make_directory(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    return _make_directory


@pytest.fixture
def make_windows_cache_env() -> MakeWindowsCacheEnv:
    def _make_windows_cache_env(root: Path) -> dict[str, str]:
        return {
            "APPDATA": str(root / "Roaming"),
            "LOCALAPPDATA": str(root / "LocalAppData"),
            "PROGRAMDATA": str(root / "ProgramData"),
            "PROGRAMFILES": str(root / "ProgramFiles"),
            "USERPROFILE": str(root / "User"),
        }

    return _make_windows_cache_env


def load_json_file(path: Path) -> JSONPayload:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


@pytest.fixture
def read_json_file() -> ReadJSONFile:
    return load_json_file


@pytest.fixture
def read_jsonl_record() -> ReadJSONLRecord:
    def _read_jsonl_record(path: Path) -> JSONPayload:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert isinstance(payload, dict)
        return payload

    return _read_jsonl_record


@pytest.fixture
def write_json_file() -> WriteJSONFile:
    def _write_json_file(path: Path, payload: JSONPayload) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    return _write_json_file


@pytest.fixture
def make_temp_plan_fixture(write_text_file: WriteTextFile) -> MakeTempPlan:
    def _make_temp_plan_fixture(tmp_path: Path, test_mode: bool = False) -> TempPlanFixture:
        temp_root = tmp_path / "Temp"
        target = write_text_file(temp_root / "stale.tmp", "x")
        env = {"TEMP": str(temp_root), "TMP": str(temp_root)}
        if test_mode:
            env["CLEANWIN_TEST_MODE"] = "1"
        return temp_root, target, env

    return _make_temp_plan_fixture


@pytest.fixture
def run_cleanwin(repo_root: Path) -> RunCleanWin:
    def _run_cleanwin(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)
        merged_env["PYTHONPATH"] = str(repo_root)
        return subprocess.run(
            [sys.executable, str(repo_root / "cleanwin.py"), "--json", *args],
            cwd=repo_root,
            env=merged_env,
            text=True,
            capture_output=True,
            check=False,
        )

    return _run_cleanwin


def load_json_stdout(result: subprocess.CompletedProcess[str]) -> JSONPayload:
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


@pytest.fixture
def cleanwin_result_json() -> CleanWinResultJSON:
    return load_json_stdout


@pytest.fixture
def cleanwin_json(run_cleanwin: RunCleanWin) -> CleanWinJSON:
    def _cleanwin_json(*args: str, env: dict[str, str] | None = None) -> JSONPayload:
        result = run_cleanwin(*args, env=env)
        assert result.returncode == 0, result.stderr
        return load_json_stdout(result)

    return _cleanwin_json


@pytest.fixture
def cleanwin_plan_file(run_cleanwin: RunCleanWin) -> CleanWinPlanFile:
    def _cleanwin_plan_file(plan_file: Path, *args: str, env: dict[str, str] | None = None) -> JSONPayload:
        result = run_cleanwin("plan", *args, "--output", str(plan_file), env=env)
        assert result.returncode == 0, result.stderr
        return load_json_file(plan_file)

    return _cleanwin_plan_file


@pytest.fixture
def assert_plan_file_valid(cleanwin_json: CleanWinJSON) -> AssertPlanFileValid:
    def _assert_plan_file_valid(plan_file: Path, env: dict[str, str]) -> JSONPayload:
        payload = cleanwin_json("validate-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
        assert payload["valid"]
        return payload

    return _assert_plan_file_valid


@pytest.fixture
def assert_dry_run_result() -> AssertDryRunResult:
    def _assert_dry_run_result(payload: JSONPayload, target: Path) -> JSONPayload:
        assert payload["results"] == [{"status": "dry-run", "path": str(target), "mode": "recycle"}]
        assert target.exists()
        return payload

    return _assert_dry_run_result


@pytest.fixture
def assert_cli_provider_schema(cleanwin_json: CleanWinJSON) -> AssertCliProviderSchema:
    def _assert_cli_provider_schema(command: str, schema: str) -> None:
        assert cleanwin_json(command)["schema"] == schema
        assert cleanwin_json("ai-tools", "--provider", command)["schema"] == schema

    return _assert_cli_provider_schema


@pytest.fixture
def assert_cli_provider_schema_with_env(cleanwin_json: CleanWinJSON) -> AssertCliProviderSchemaWithEnv:
    def _assert_cli_provider_schema_with_env(command: str, schema: str, env: dict[str, str]) -> None:
        assert cleanwin_json(command, env=env)["schema"] == schema
        assert cleanwin_json("ai-tools", "--provider", command, env=env)["schema"] == schema

    return _assert_cli_provider_schema_with_env


@pytest.fixture
def assert_cli_provider_schemas(assert_cli_provider_schema: AssertCliProviderSchema) -> AssertCliProviderSchemas:
    def _assert_cli_provider_schemas(pairs: SchemaPairs) -> None:
        for command, schema in pairs:
            assert_cli_provider_schema(command, schema)

    return _assert_cli_provider_schemas


@pytest.fixture
def assert_cli_provider_schema_sample(
    assert_cli_provider_schema: AssertCliProviderSchema,
    assert_schema_sample: AssertSchemaSample,
) -> AssertCliProviderSchemaSample:
    def _assert_cli_provider_schema_sample(command: str, schema: str) -> JSONPayload:
        assert_cli_provider_schema(command, schema)
        return assert_schema_sample(schema)

    return _assert_cli_provider_schema_sample


@pytest.fixture
def assert_ai_provider_schema(cleanwin_json: CleanWinJSON) -> AssertAIProviderSchema:
    def _assert_ai_provider_schema(provider: str, schema: str) -> None:
        assert cleanwin_json("ai-tools", "--provider", provider)["schema"] == schema

    return _assert_ai_provider_schema


@pytest.fixture
def assert_ai_provider_schema_with_env(cleanwin_json: CleanWinJSON) -> AssertAIProviderSchemaWithEnv:
    def _assert_ai_provider_schema_with_env(provider: str, schema: str, env: dict[str, str]) -> None:
        assert cleanwin_json("ai-tools", "--provider", provider, env=env)["schema"] == schema

    return _assert_ai_provider_schema_with_env


@pytest.fixture
def assert_ai_provider_schemas(assert_ai_provider_schema: AssertAIProviderSchema) -> AssertAIProviderSchemas:
    def _assert_ai_provider_schemas(pairs: SchemaPairs) -> None:
        for provider, schema in pairs:
            assert_ai_provider_schema(provider, schema)

    return _assert_ai_provider_schemas


@pytest.fixture
def assert_payload_schema() -> AssertPayloadSchema:
    def _assert_payload_schema(payload: JSONPayload, schema: str) -> JSONPayload:
        assert payload["schema"] == schema
        return payload

    return _assert_payload_schema


@pytest.fixture
def assert_schemas_registered(cleanwin_json: CleanWinJSON) -> AssertSchemasRegistered:
    def _assert_schemas_registered(schemas: list[str]) -> None:
        registry = cleanwin_json("schema-registry")
        names = {entry["name"] for entry in registry["entries"]}
        for schema in schemas:
            assert schema in names

    return _assert_schemas_registered


@pytest.fixture
def assert_schema_sample(cleanwin_json: CleanWinJSON) -> AssertSchemaSample:
    def _assert_schema_sample(schema: str) -> JSONPayload:
        registry = cleanwin_json("schema-registry")
        assert schema in {entry["name"] for entry in registry["entries"]}
        sample = registry["samples"][schema]
        assert sample["schema"] == schema
        return sample

    return _assert_schema_sample


@pytest.fixture
def assert_schema_samples(assert_schema_sample: AssertSchemaSample) -> AssertSchemaSamples:
    def _assert_schema_samples(schemas: Sequence[str]) -> dict[str, JSONPayload]:
        return {schema: assert_schema_sample(schema) for schema in schemas}

    return _assert_schema_samples


@pytest.fixture
def assert_readonly_schema_sample(assert_schema_sample: AssertSchemaSample) -> AssertReadonlySchemaSample:
    def _assert_readonly_schema_sample(schema: str) -> JSONPayload:
        sample = assert_schema_sample(schema)
        if "destructive" in sample:
            assert sample["destructive"] is False
        if "executes_system_commands" in sample:
            assert sample["executes_system_commands"] is False
        return sample

    return _assert_readonly_schema_sample


@pytest.fixture
def assert_readonly_report() -> AssertReadonlyReport:
    def _assert_readonly_report(report: JSONPayload, schema: str) -> JSONPayload:
        assert report["schema"] == schema
        assert report["destructive"] is False
        if "dry_run" in report:
            assert report["dry_run"] is True
        if "executes_system_commands" in report:
            assert report["executes_system_commands"] is False
        return report

    return _assert_readonly_report


@pytest.fixture
def assert_execution_disabled() -> AssertExecutionDisabled:
    def _assert_execution_disabled(payload: JSONPayload, *fields: str) -> JSONPayload:
        for field in ("execution_enabled", "auto_executable", "executes_by_report", *fields):
            if field in payload:
                assert payload[field] is False
        return payload

    return _assert_execution_disabled


@pytest.fixture
def assert_safe_to_execute_disabled() -> AssertSafeToExecuteDisabled:
    def _assert_safe_to_execute_disabled(payload: JSONPayload) -> JSONPayload:
        assert payload["safe_to_execute"] is False
        return payload

    return _assert_safe_to_execute_disabled


@pytest.fixture
def assert_command_sequence() -> AssertCommandSequence:
    def _is_unittest_command(command: str | Sequence[str]) -> bool:
        if isinstance(command, str):
            return "unittest" in command.lower()
        return list(command[:3]) == ["python3", "-m", "unittest"]

    def _assert_command_sequence(commands: CommandSequence, required: CommandSequence = ()) -> None:
        assert not [command for command in commands if _is_unittest_command(command)]
        for command in required:
            assert command in commands

    return _assert_command_sequence
