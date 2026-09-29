#!/usr/bin/env python3
"""Offline validator for SRS-writing agent outputs.

Static checks against a completed (or in-progress) SRS run directory:

  - progress.json: valid structure, unique requirement IDs, ID format
    ``F-<chapter>-<seq>``, stage traceability.
  - Every accepted requirement maps back to a registered function item
    (forward direction) and has a task-book chapter source.
  - Every function item has at least one accepted requirement, unless it is
    explicitly declared in the ``gaps`` list.
  - Final .docx artifacts exist and are non-empty; rejected requirement IDs
    do not leak into the generated SRS document.
  - Every accepted requirement ID appears in both final .docx artifacts
    (SRS body and traceability matrix).
  - ``requirement-catalog.md`` exists and its requirement-ID set matches
    progress.json exactly.
  - A finished run (stage ``review``/``complete``) leaves no pending
    (non-terminal) requirements.

Findings are graded: errors (``fail``) block delivery and decide the exit
code; warnings (``warn``, e.g. vague wording like 及时/适当/高效/尽量 in
accepted requirement descriptions) are reported but never block.

Dependencies: stdlib only. Usage:

    python /mnt/skills/srs-writing/scripts/validate_srs_outputs.py --outputs-dir /mnt/user-data/outputs

When the outputs directory has no progress.json of its own, each one-level
subdirectory holding one is validated as an independent per-task-book run
(any failing run fails the whole validation).

Exit code 0 when there are no errors (warnings do not affect it).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

REQ_ID_RE = re.compile(r"^F-\d+(?:\.\d+)*-\d+$")
CATALOG_ID_RE = re.compile(r"F-\d+(?:\.\d+)*-\d+")

# GJB438C-2021 需求表述规范：避免「及时、适当、高效、尽量」等无量化约束的歧义词。
VAGUE_WORDS: tuple[str, ...] = ("及时", "适当", "高效", "尽量")

# Terminal requirement statuses; anything else counts as pending (undecided).
TERMINAL_STATUSES = frozenset({"accepted", "modified", "rejected"})
# Finished-run stages: a run in one of these stages must not leave pending items.
FINAL_STAGES = frozenset({"review", "complete"})

CHECK_FAILURES: list[str] = []
WARNINGS: list[str] = []


def fail(msg: str) -> None:
    CHECK_FAILURES.append(msg)


def warn(msg: str) -> None:
    WARNINGS.append(msg)


def ok(msg: str) -> None:
    print(f"  [ok] {msg}")


def load_progress(outputs: Path) -> dict:
    path = outputs / "progress.json"
    if not path.exists():
        fail(f"missing progress.json under {outputs}")
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        fail(f"progress.json is not valid JSON: {exc}")
        return {}
    if not isinstance(data, dict):
        fail("progress.json top-level must be an object")
        return {}
    return data


def check_id_uniqueness(requirements: list[dict]) -> None:
    seen: dict[str, int] = {}
    for req in requirements:
        rid = str(req.get("id", "")).strip()
        if not rid:
            fail("a requirement is missing its ID")
            continue
        if not REQ_ID_RE.match(rid):
            fail(f"requirement ID {rid!r} does not match F-<chapter>-<seq> format")
            continue
        seen[rid] = seen.get(rid, 0) + 1
    dupes = {rid for rid, n in seen.items() if n > 1}
    if dupes:
        fail(f"duplicate requirement IDs: {sorted(dupes)}")


def _accepted_reqs(requirements: list[dict]) -> list[dict]:
    return [r for r in requirements if r.get("status", "").lower() in {"accepted", "modified"}]


def check_traceability(data: dict) -> None:
    functions = {f.get("id"): f for f in data.get("functions", []) if f.get("id")}
    requirements = data.get("requirements", [])
    accepted = _accepted_reqs(requirements)

    declared_gaps = {g.get("function_id") for g in data.get("gaps", []) if g.get("function_id")}
    declared_gaps |= {g for g in data.get("declared_gaps", [])}

    covered: set[str] = set()
    for req in accepted:
        rid = str(req.get("id", req.get("ID", ""))).strip()
        src = req.get("source_function") or req.get("function_id")
        chapter = req.get("source_chapter") or req.get("taskbook_chapter") or ""
        if not src:
            fail(f"accepted requirement {rid} has no source function item (forward trace broken)")
            continue
        if not chapter:
            fail(f"accepted requirement {rid} has no task-book chapter source (reverse trace broken)")
        if src not in functions:
            fail(f"accepted requirement {rid} references unknown function item {src!r}")
            continue
        covered.add(src)

    uncovered = [fid for fid in functions if fid not in covered and fid not in declared_gaps]
    if uncovered:
        fail(f"function items with no accepted requirement (undeclared gaps): {sorted(uncovered)}")


def check_vague_words(data: dict) -> None:
    """Warn (non-blocking) when accepted/modified descriptions use vague wording."""
    for req in _accepted_reqs(data.get("requirements", [])):
        rid = str(req.get("id") or req.get("ID") or "").strip()
        description = str(req.get("description", ""))
        hits = [word for word in VAGUE_WORDS if word in description]
        if hits:
            warn(f"requirement {rid} description contains vague wording: {', '.join(hits)}")


# Known limitations of matching IDs against the raw XML text (accepted for
# now, not fixed here): IDs inside XML comments, attributes, or bookmark names
# also count as "present", and Word re-editing can split one ID across several
# <w:t> runs, causing a false "missing" report.
def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            with zf.open("word/document.xml") as fh:
                return fh.read().decode("utf-8", errors="replace")
    except (KeyError, zipfile.BadZipFile, OSError) as exc:
        fail(f"cannot read docx {path.name}: {exc}")
        return ""


def check_artifacts(outputs: Path, data: dict) -> None:
    srs = outputs / "srs_document.docx"
    matrix = outputs / "traceability-matrix.docx"
    for artifact in (srs, matrix):
        if not artifact.exists():
            fail(f"missing {artifact.name}")
        elif artifact.stat().st_size == 0:
            fail(f"{artifact.name} is empty")

    rejected_ids = [r.get("id") or r.get("ID") for r in data.get("requirements", []) if r.get("status", "").lower() == "rejected"]
    if rejected_ids and srs.exists() and srs.stat().st_size:
        text = _docx_text(srs)
        present = [rid for rid in rejected_ids if rid and rid in text]
        if present:
            fail(f"rejected requirement IDs appear in srs_document.docx: {present}")


def check_id_presence(outputs: Path, data: dict) -> None:
    """Every accepted requirement ID must appear in both final .docx artifacts."""
    texts: dict[str, str] = {}
    for name in ("srs_document.docx", "traceability-matrix.docx"):
        path = outputs / name
        # Files that are missing or zero-byte are already reported by
        # check_artifacts; only artifacts past those checks are inspected here.
        if path.exists() and path.stat().st_size:
            text = _docx_text(path)
            if text:
                texts[name] = text
            else:
                # A valid zip with zero body text must not be skipped silently:
                # every ID check below would otherwise pass vacuously.
                fail(f"no readable text in {name}")
    for req in _accepted_reqs(data.get("requirements", [])):
        rid = str(req.get("id") or req.get("ID") or "").strip()
        if not rid:
            continue
        for name, text in texts.items():
            if rid not in text:
                fail(f"accepted requirement {rid} does not appear in {name}")


def check_requirement_catalog(outputs: Path, data: dict) -> None:
    """requirement-catalog.md must exist and its ID set must match progress.json."""
    catalog = outputs / "requirement-catalog.md"
    if not catalog.exists():
        fail("missing requirement-catalog.md")
        return
    try:
        text = catalog.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fail(f"cannot read requirement-catalog.md: {exc}")
        return
    progress_ids = {str(r.get("id") or r.get("ID") or "").strip() for r in data.get("requirements", [])}
    progress_ids.discard("")
    catalog_ids = set(CATALOG_ID_RE.findall(text))
    missing = sorted(progress_ids - catalog_ids)
    if missing:
        fail(f"requirement-catalog.md is missing requirement IDs: {missing}")
    unknown = sorted(catalog_ids - progress_ids)
    if unknown:
        fail(f"requirement-catalog.md contains IDs not in progress.json: {unknown}")


def check_pending_requirements(data: dict) -> None:
    """A finished run (review/complete stage) must not leave pending requirements."""
    stage = str(data.get("stage", "")).strip().lower()
    if stage not in FINAL_STAGES:
        return
    pending = [
        str(r.get("id") or r.get("ID") or "").strip()
        for r in data.get("requirements", [])
        if str(r.get("status", "")).strip().lower() not in TERMINAL_STATUSES
    ]
    pending = [rid for rid in pending if rid]
    if pending:
        fail(f"stage {stage!r} still has pending requirements (not accepted/modified/rejected): {pending}")


def discover_run_dirs(outputs: Path) -> list[Path]:
    """Run directories to validate under ``outputs``.

    Flat layout first: when ``outputs`` holds progress.json itself, it is the
    only run. Otherwise each one-level-deep subdirectory holding a
    progress.json is one per-task-book run; anything deeper is ignored.
    An empty result means no progress file anywhere.
    """
    if (outputs / "progress.json").exists():
        return [outputs]
    return sorted(p.parent for p in outputs.glob("*/progress.json"))


def validate_run(run_dir: Path) -> bool:
    """Run every check for one run directory and print the findings.

    False when progress.json is unreadable or any check failed.
    """
    data = load_progress(run_dir)
    if not data:
        print("FAILED: could not load progress.json")
        return False

    print("Checking requirement catalog integrity...")
    check_id_uniqueness(data.get("requirements", []))
    check_traceability(data)
    print("Checking generated .docx artifacts...")
    check_artifacts(run_dir, data)
    check_id_presence(run_dir, data)
    print("Checking requirement catalog consistency...")
    check_requirement_catalog(run_dir, data)
    check_pending_requirements(data)
    print("Checking requirement wording...")
    check_vague_words(data)

    if WARNINGS:
        print("\nWarnings (do not affect the exit code):")
        for item in WARNINGS:
            print(f"  [warn] {item}")
    if CHECK_FAILURES:
        print("\nFAILED with the following issues:")
        for item in CHECK_FAILURES:
            print(f"  - {item}")
        return False
    print("\nALL CHECKS PASSED")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SRS-writing agent outputs.")
    parser.add_argument("--outputs-dir", default="/mnt/user-data/outputs", help="Directory holding the SRS outputs")
    args = parser.parse_args()

    outputs = Path(args.outputs_dir)
    print(f"Validating outputs under {outputs}")
    if not outputs.is_dir():
        print("FAILED: outputs directory not found")
        return 1

    run_dirs = discover_run_dirs(outputs)
    if not run_dirs:
        # Neither the directory itself nor a one-level task-book subdirectory
        # holds progress.json: keep the flat-layout failure semantics.
        load_progress(outputs)
        print("FAILED: could not load progress.json")
        return 1
    if len(run_dirs) == 1:
        # Flat layout and single-task-book subdirectory behave identically.
        return 0 if validate_run(run_dirs[0]) else 1

    # Several task books ran in parallel: validate each subdirectory in turn,
    # labeling the findings with the directory name; any failure fails all.
    passed = 0
    for run_dir in run_dirs:
        CHECK_FAILURES.clear()
        WARNINGS.clear()
        print(f"\n--- {run_dir.name} ---")
        if validate_run(run_dir):
            passed += 1
    failed = len(run_dirs) - passed
    if failed:
        print(f"\nFAILED: {failed} of {len(run_dirs)} task-book runs failed validation")
        return 1
    print(f"\nAll {len(run_dirs)} task-book runs passed validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())