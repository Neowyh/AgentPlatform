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

Dependencies: stdlib only. Usage:

    python scripts/validate_srs_outputs.py --outputs-dir /mnt/user-data/outputs

Exit code 0 when all checks pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

REQ_ID_RE = re.compile(r"^F-\d+(?:\.\d+)*-\d+$")

CHECK_FAILURES: list[str] = []


def fail(msg: str) -> None:
    CHECK_FAILURES.append(msg)


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SRS-writing agent outputs.")
    parser.add_argument("--outputs-dir", default="/mnt/user-data/outputs", help="Directory holding the SRS outputs")
    args = parser.parse_args()

    outputs = Path(args.outputs_dir)
    print(f"Validating outputs under {outputs}")
    if not outputs.is_dir():
        print("FAILED: outputs directory not found")
        return 1

    data = load_progress(outputs)
    if not data:
        print("FAILED: could not load progress.json")
        return 1

    print("Checking requirement catalog integrity...")
    check_id_uniqueness(data.get("requirements", []))
    check_traceability(data)
    print("Checking generated .docx artifacts...")
    check_artifacts(outputs, data)

    if CHECK_FAILURES:
        print("\nFAILED with the following issues:")
        for item in CHECK_FAILURES:
            print(f"  - {item}")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())