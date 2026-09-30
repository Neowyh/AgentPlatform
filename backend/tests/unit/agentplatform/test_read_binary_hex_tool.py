"""S3 seam: the ``read_binary_hex`` tool over whitelisted binary evidence.

Ticket 03: the tool is the model's only entry to the binary evidence (firmware
images, build artifacts) the code-evidence pipeline now accepts. It accepts
nothing but a file path inside this thread's package source tree, renders a
fixed three-column hex + printable-ASCII view (xxd-style) with
``offset``/``length`` paging, and rejects anything else structurally:
paths outside the package, unknown packages, oversized binaries and
non-binary files.

Everything here drives the tool coroutine directly (the builtin-tool test
convention) against a seeded package on a temporary filesystem home.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agentplatform import code_evidence
from app.agentplatform.tools import read_binary_hex_tool as tool_module
from deerflow.config.paths import Paths

FIRMWARE = b"\x7fELF-firmware"


def _runtime(thread_id: str = "thread-1", user_id: str = "owner-1") -> SimpleNamespace:
    context: dict = {"thread_id": thread_id, "user_id": user_id, "user_role": "user"}
    return SimpleNamespace(state=None, context=context, config={"configurable": {"thread_id": thread_id}})


def _package_source_dir(env, thread_id: str = "thread-1", package_id: str = "pkg-1") -> object:
    return env.paths.thread_dir(thread_id, user_id="owner-1") / "user-data" / "code-evidence" / package_id / "source"


def _seed_binary(env, name: str = "firmware.bin", payload: bytes = FIRMWARE, package_id: str = "pkg-1") -> None:
    source = _package_source_dir(env, package_id=package_id)
    source.mkdir(parents=True, exist_ok=True)
    (source / name).write_bytes(payload)


@pytest.fixture
def env(tmp_path, monkeypatch):
    paths = Paths(tmp_path)
    monkeypatch.setattr("app.agentplatform.code_evidence.get_paths", lambda: paths)
    return SimpleNamespace(paths=paths, tmp_path=tmp_path, monkeypatch=monkeypatch)


async def _call(runtime, file_path: str, **kwargs) -> dict:
    raw = await tool_module.read_binary_hex_tool.coroutine(runtime=runtime, file_path=file_path, **kwargs)
    return json.loads(raw)


@pytest.mark.asyncio
async def test_renders_hex_and_ascii_view_for_package_binary(env) -> None:
    _seed_binary(env)

    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1/source/firmware.bin")

    assert payload["package_id"] == "pkg-1"
    assert payload["file_size"] == len(FIRMWARE)
    assert payload["offset"] == 0
    assert payload["length"] == len(FIRMWARE)
    assert payload["truncated"] is False
    assert payload["has_more"] is False
    assert payload["max_view_bytes"] == tool_module.MAX_VIEW_BYTES
    assert payload["hex_view"] == "00000000  7f 45 4c 46 2d 66 69 72  6d 77 61 72 65          |.ELF-firmware|"
    assert "next_action" in payload


@pytest.mark.asyncio
async def test_pages_with_offset_and_length(env) -> None:
    _seed_binary(env, name="blob.bin", payload=bytes(range(32)))

    second_page = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1/source/blob.bin", offset=16, length=16)
    assert second_page["offset"] == 16
    assert second_page["length"] == 16
    assert second_page["hex_view"] == "00000010  10 11 12 13 14 15 16 17  18 19 1a 1b 1c 1d 1e 1f |................|"
    assert second_page["has_more"] is False

    first_page = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1/source/blob.bin", offset=0, length=8)
    assert first_page["length"] == 8
    assert first_page["has_more"] is True
    assert first_page["hex_view"] == "00000000  00 01 02 03 04 05 06 07                          |........|"


@pytest.mark.asyncio
async def test_length_beyond_single_output_limit_is_truncated_with_notice(env, monkeypatch) -> None:
    _seed_binary(env, name="blob.bin", payload=bytes(range(32)))
    monkeypatch.setattr(tool_module, "MAX_VIEW_BYTES", 8)

    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1/source/blob.bin", length=100)

    assert payload["length"] == 8
    assert payload["truncated"] is True
    assert payload["max_view_bytes"] == 8
    assert payload["has_more"] is True


@pytest.mark.asyncio
async def test_offset_past_end_of_file_returns_empty_view(env) -> None:
    _seed_binary(env)

    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1/source/firmware.bin", offset=999)

    assert payload["offset"] == 999
    assert payload["length"] == 0
    assert payload["hex_view"] == ""
    assert payload["has_more"] is False


@pytest.mark.asyncio
async def test_paths_outside_the_package_source_tree_are_structurally_rejected(env) -> None:
    _seed_binary(env)

    for declared in [
        "/mnt/user-data/uploads/evidence.bin",
        "/mnt/user-data/code-evidence/pkg-1/manifest.json",
        "/mnt/user-data/code-evidence/pkg-1/source",
        "/mnt/user-data/code-evidence/pkg-1/source/../../etc/passwd",
        "/etc/passwd",
        "",
    ]:
        payload = await _call(_runtime(), declared)
        assert payload["reason_code"] == "file_path_rejected", declared
        assert payload["allowed_pattern"] == "/mnt/user-data/code-evidence/<package_id>/source/<file>"
        assert "error" in payload


@pytest.mark.asyncio
async def test_unknown_package_is_reported_not_raised(env) -> None:
    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/missing-pkg/source/firmware.bin")

    assert payload["reason_code"] == "package_not_found"
    assert "missing-pkg" in payload["error"]


@pytest.mark.asyncio
async def test_thread_context_is_required(env) -> None:
    runtime = _runtime()
    runtime.context = {}
    runtime.config = {"configurable": {}}

    payload = await _call(runtime, "/mnt/user-data/code-evidence/pkg-1/source/firmware.bin")

    assert payload["reason_code"] == "thread_context_missing"


@pytest.mark.asyncio
async def test_missing_file_inside_package_is_reported(env) -> None:
    _seed_binary(env)

    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1/source/nope.bin")

    assert payload["reason_code"] == "file_not_found"
    assert "nope.bin" in payload["error"]


@pytest.mark.asyncio
async def test_non_binary_file_is_rejected_with_read_file_hint(env) -> None:
    source = _package_source_dir(env)
    source.mkdir(parents=True, exist_ok=True)
    (source / "main.c").write_text("int main(void) { return 0; }", encoding="utf-8")

    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1/source/main.c")

    assert payload["reason_code"] == "not_binary_evidence"
    assert "read_file" in payload["error"]


@pytest.mark.asyncio
async def test_oversized_binary_is_rejected_with_same_source_limit(env, monkeypatch) -> None:
    _seed_binary(env)
    monkeypatch.setattr(code_evidence, "BINARY_EVIDENCE_MAX_BYTES", 4)

    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1/source/firmware.bin")

    assert payload["reason_code"] == "file_too_large"
    assert "4" in payload["error"]
    assert "binary" in payload["error"].lower()
