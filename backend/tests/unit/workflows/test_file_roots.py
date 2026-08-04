from __future__ import annotations

from pathlib import Path

import pytest

from ideer.config.paths import Paths
from ideer.workflows.v2 import file_roots
from ideer.workflows.v2.file_roots import (
    collect_artifacts,
    make_host_resolver,
    missing_written_artifacts,
    render_roots,
    render_template,
    validate_roots,
)


class FakeMount:
    def __init__(self, container_path: str, host_path: str, read_only: bool = False) -> None:
        self.container_path = container_path
        self.host_path = host_path
        self.read_only = read_only


@pytest.fixture
def custom_mounts(monkeypatch):
    mounts = [
        FakeMount("/mnt/eval-cases", "/host/eval-cases", read_only=True),
        FakeMount("/mnt/fault-zeroing-outputs", "/host/outputs", read_only=False),
    ]
    monkeypatch.setattr(file_roots, "_get_custom_mounts", lambda: mounts)
    return mounts


@pytest.fixture
def host_resolver(monkeypatch, tmp_path: Path):
    base = Paths(str(tmp_path / "base"))
    monkeypatch.setattr(file_roots, "get_paths", lambda: base)
    return base


class TestRenderTemplate:
    def test_plain_value_passes_through(self) -> None:
        assert render_template("no template", {"inputs": {}}) == "no template"
        assert render_template(42, {}) == 42

    def test_nested_structures_are_rendered_recursively(self) -> None:
        state = {"inputs": {"dir": "/mnt/user-data/outputs"}}
        assert render_template(
            {"read": ["{{inputs.dir}}/a.json"], "write": [{"x": "{{inputs.dir}}/b.md"}]},
            state,
        ) == {"read": ["/mnt/user-data/outputs/a.json"], "write": [{"x": "/mnt/user-data/outputs/b.md"}]}

    def test_state_path_resolution(self) -> None:
        state = {"state": {"attempt": 3}}
        assert render_template("run-{{state.attempt}}", state) == "run-3"

    def test_none_value_keeps_template_verbatim(self) -> None:
        state = {"inputs": {"upload_dir": None}}
        assert render_template("{{inputs.upload_dir}}/a.json", state) == "{{inputs.upload_dir}}/a.json"


class TestRenderRoots:
    def test_missing_template_value_keeps_root_verbatim(self) -> None:
        rendered = render_roots(
            {"read": ["{{state.late}}/x.json"], "write": []},
            {"inputs": {}, "state": {}},
        )
        assert rendered == {"read": ["{{state.late}}/x.json"], "write": []}

    def test_none_file_access_returns_none(self) -> None:
        assert render_roots(None, {}) is None


class TestValidateRoots:
    def test_user_data_roots_are_valid(self, custom_mounts) -> None:
        assert (
            validate_roots(
                {
                    "read": ["/mnt/user-data/uploads", "/mnt/user-data/outputs/a.json"],
                    "write": ["/mnt/user-data/outputs/artifacts/b.json"],
                }
            )
            == []
        )

    def test_host_path_roots_are_rejected(self, custom_mounts) -> None:
        invalid = validate_roots({"read": [], "write": ["/home/user/out.json", "/tmp/x.json"]})
        assert invalid == ["write:/home/user/out.json", "write:/tmp/x.json"]

    def test_write_to_readonly_areas_is_rejected(self, custom_mounts) -> None:
        invalid = validate_roots(
            {
                "read": ["/mnt/skills/custom/fault-zeroing", "/mnt/acp-workspace/x"],
                "write": ["/mnt/skills/custom/x.json", "/mnt/acp-workspace/y", "/mnt/eval-cases/z.json"],
            }
        )
        assert invalid == ["write:/mnt/skills/custom/x.json", "write:/mnt/acp-workspace/y", "write:/mnt/eval-cases/z.json"]

    def test_writable_custom_mount_is_allowed(self, custom_mounts) -> None:
        assert validate_roots({"read": [], "write": ["/mnt/fault-zeroing-outputs/run1/a.json"]}) == []

    def test_unresolved_templates_are_skipped(self, custom_mounts) -> None:
        assert validate_roots({"read": [], "write": ["{{state.dir}}/a.json"]}) == []


class TestHostResolver:
    def test_user_data_mapping(self, host_resolver, tmp_path: Path) -> None:
        resolver = make_host_resolver("run-1", "user-1")
        expected = str(host_resolver.sandbox_outputs_dir("run-1", user_id="user-1"))
        assert resolver("/mnt/user-data/outputs/artifacts/a.json") == f"{expected}/artifacts/a.json"
        assert resolver("/mnt/user-data/workspace") == str(host_resolver.sandbox_work_dir("run-1", user_id="user-1"))

    def test_custom_mount_mapping(self, custom_mounts) -> None:
        resolver = make_host_resolver("run-1", "user-1")
        assert resolver("/mnt/eval-cases/case_01") == "/host/eval-cases/case_01"
        assert resolver("/mnt/fault-zeroing-outputs/x.json") == "/host/outputs/x.json"

    def test_unresolvable_path_returns_none(self, custom_mounts) -> None:
        resolver = make_host_resolver("run-1", "user-1")
        assert resolver("/etc/passwd") is None
        assert resolver("/mnt/unknown/x.json") is None


class TestMissingWrittenArtifacts:
    def _write(self, path: Path, content: str = "data") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_file_root_present_and_non_empty_passes(self, tmp_path: Path) -> None:
        self._write(tmp_path / "out" / "a.json")
        assert missing_written_artifacts([str(tmp_path / "out" / "a.json")], lambda p: p) == []

    def test_missing_or_empty_file_is_reported(self, tmp_path: Path) -> None:
        self._write(tmp_path / "out" / "empty.json", "")
        missing = missing_written_artifacts(
            [str(tmp_path / "out" / "gone.json"), str(tmp_path / "out" / "empty.json")],
            lambda p: p,
        )
        assert missing == [str(tmp_path / "out" / "gone.json"), str(tmp_path / "out" / "empty.json")]

    def test_directory_root_only_checks_existence(self, tmp_path: Path) -> None:
        missing = missing_written_artifacts([f"{tmp_path / 'out' / 'tree'}/"], lambda p: p)
        assert missing == [f"{tmp_path / 'out' / 'tree'}/"]
        (tmp_path / "out" / "tree").mkdir(parents=True)
        assert missing_written_artifacts([f"{tmp_path / 'out' / 'tree'}/"], lambda p: p) == []

    def test_unresolvable_root_is_reported_missing(self, custom_mounts) -> None:
        assert missing_written_artifacts(["/mnt/unknown/x.json"], lambda p: None) == ["/mnt/unknown/x.json"]


class TestCollectArtifacts:
    def _write(self, path: Path, content: str = "data") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_directory_root_expands_recursively(self, tmp_path: Path) -> None:
        self._write(tmp_path / "out" / "a.json")
        self._write(tmp_path / "out" / "sub" / "b.md")

        def resolver(p: str) -> str | None:
            return str(tmp_path / "out") if p.rstrip("/") == "/mnt/user-data/outputs/artifacts" else None

        artifacts = collect_artifacts(["/mnt/user-data/outputs/artifacts/"], resolver)
        assert [item["path"] for item in artifacts] == [
            "/mnt/user-data/outputs/artifacts/a.json",
            "/mnt/user-data/outputs/artifacts/sub/b.md",
        ]
        assert all(item["size"] == 4 for item in artifacts)

    def test_file_root_lists_single_file(self, tmp_path: Path) -> None:
        self._write(tmp_path / "out" / "a.json")

        def resolver(p: str) -> str | None:
            return str(tmp_path / "out" / "a.json")

        artifacts = collect_artifacts(["/mnt/user-data/outputs/a.json"], resolver)
        assert [item["path"] for item in artifacts] == ["/mnt/user-data/outputs/a.json"]
        assert artifacts[0]["size"] == 4

    def test_unresolvable_root_is_skipped(self, tmp_path: Path) -> None:
        self._write(tmp_path / "out" / "a.json")

        def resolver(p: str) -> str | None:
            return str(tmp_path / "out" / "a.json") if p.endswith("a.json") else None

        artifacts = collect_artifacts(["/mnt/unknown/x.json", "/mnt/user-data/outputs/a.json"], resolver)
        assert [item["path"] for item in artifacts] == ["/mnt/user-data/outputs/a.json"]

    def test_overlapping_roots_are_deduplicated(self, tmp_path: Path) -> None:
        self._write(tmp_path / "out" / "a.json")

        def resolver(p: str) -> str | None:
            return str(tmp_path / "out" / "a.json")

        artifacts = collect_artifacts(["/mnt/user-data/outputs/a.json", "/mnt/user-data/outputs/a.json"], resolver)
        assert len(artifacts) == 1

    def test_sorted_by_virtual_path(self, tmp_path: Path) -> None:
        self._write(tmp_path / "out" / "b.md")
        self._write(tmp_path / "out" / "a.json")

        def resolver(p: str) -> str | None:
            return str(tmp_path / "out") if p.rstrip("/") == "/mnt/user-data/outputs" else None

        artifacts = collect_artifacts(["/mnt/user-data/outputs/"], resolver)
        assert [item["path"] for item in artifacts] == [
            "/mnt/user-data/outputs/a.json",
            "/mnt/user-data/outputs/b.md",
        ]
