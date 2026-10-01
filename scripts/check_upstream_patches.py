#!/usr/bin/env python3
"""Check upstream patch registration and current verification evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "backend/packages/harness/deerflow/"
REGISTRY_PATTERN = re.compile(
    r"<!-- upstream-registry:start -->\s*```json\s*(.*?)\s*```\s*<!-- upstream-registry:end -->",
    re.DOTALL,
)
REQUIRED_TEXT_FIELDS = (
    "reason",
    "alternative",
    "impact",
    "owner",
    "removal",
)


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _commit(root: Path, reference: str, label: str) -> str:
    if not reference or reference.startswith("-"):
        raise ValueError(f"invalid {label} revision: {reference!r}")
    resolved = (
        git(
            root,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{reference}^{{commit}}",
        )
        .decode("ascii", errors="strict")
        .strip()
    )
    if not re.fullmatch(r"[0-9a-f]{40,64}", resolved):
        raise ValueError(f"could not resolve {label} to a commit: {reference}")
    return resolved


def _registry(ledger: str, label: str) -> dict:
    match = REGISTRY_PATTERN.search(ledger)
    if not match:
        raise ValueError(f"{label}: missing structured registry in root ledger")
    try:
        registry = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid registry JSON: {exc}") from exc
    if not isinstance(registry, dict):
        raise TypeError(f"{label}: registry must be a JSON object")
    return registry


def _read_worktree_ledger(root: Path) -> str:
    try:
        return (root / "UPSTREAM_PATCH_LEDGER.md").read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read root patch ledger: {exc}") from exc


def _read_ref_ledger(root: Path, ref: str, *, optional: bool = False) -> str | None:
    pathspec = f"{ref}:UPSTREAM_PATCH_LEDGER.md"
    exists = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", pathspec],
        capture_output=True,
        check=False,
    )
    if exists.returncode:
        if optional:
            return None
        raise ValueError(f"{ref} has no UPSTREAM_PATCH_LEDGER.md")
    try:
        return git(root, "show", pathspec).decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ValueError(f"{ref}: root patch ledger is not UTF-8") from exc


def _name_set(output: bytes) -> set[str]:
    try:
        return {item.decode("utf-8", errors="strict") for item in output.split(b"\0") if item}
    except UnicodeError as exc:
        raise ValueError("harness paths must be UTF-8") from exc


def _diff_paths(root: Path, left: str, right: str | None) -> set[str]:
    args = ["diff", "--no-renames", "--name-only", "-z", left]
    if right:
        args.append(right)
    args.extend(["--", PREFIX])
    paths = _name_set(git(root, *args))
    if right is None:
        paths.update(
            _name_set(
                git(
                    root,
                    "ls-files",
                    "--others",
                    "--exclude-standard",
                    "-z",
                    "--",
                    PREFIX,
                )
            )
        )
    return paths


def _entry_map(registry: Mapping[str, object], label: str, errors: list[str]) -> dict[str, dict]:
    entries = registry.get("patches")
    if not isinstance(entries, list):
        errors.append(f"{label}: registry patches must be an array")
        return {}
    result: dict[str, dict] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"{label}: patch entry {index} must be an object")
            continue
        patch_id = entry.get("id")
        if not isinstance(patch_id, str) or not patch_id.strip():
            errors.append(f"{label}: patch entry {index} has no id")
            continue
        if patch_id in result:
            errors.append(f"{label}: duplicate id: {patch_id}")
            continue
        result[patch_id] = entry
    return result


def _valid_path(path: object) -> tuple[bool, str]:
    if not isinstance(path, str) or not path:
        return False, str(path)
    if "\\" in path:
        return False, path
    pure = PurePosixPath(path)
    if not path.startswith(PREFIX) or pure.is_absolute() or ".." in pure.parts or not pure.suffix:
        return False, path
    return True, path


def _placeholder(value: str) -> bool:
    return bool(re.match(r"\s*(?:see\s+)?PATCH-\d+(?:\.\.|\s)*(?:rationale|reason|details?|owner|maintainer|test|verification)?\b", value, re.IGNORECASE))


def _section(ledger: str, patch_id: str) -> str | None:
    match = re.search(rf"^### {re.escape(patch_id)}:.*$", ledger, re.MULTILINE)
    if not match:
        return None
    following = re.search(r"^### PATCH-|^## Enforcement", ledger[match.end() :], re.MULTILINE)
    end = match.end() + following.start() if following else len(ledger)
    return ledger[match.start() : end]


def _section_field(section: str, label: str) -> str:
    match = re.search(
        rf"^- \*\*{re.escape(label)}\*\*:\s*(.*?)(?=\n- \*\*|\Z)",
        section,
        re.MULTILINE | re.DOTALL,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def _ledger_metadata(ledger: str, patch_id: str) -> dict[str, str] | None:
    if patch_id in {f"PATCH-{index:03d}" for index in range(2, 16)}:
        headers = (
            "| ID | Path / symbol (impact scope) |",
            "| ID | Path / symbol |",
        )
        starts = [ledger.find(header) for header in headers]
        starts = [start for start in starts if start >= 0]
        if not starts:
            return None
        start = min(starts)
        end_match = re.search(r"^### PATCH-|^## Enforcement", ledger[start:], re.MULTILINE)
        table = ledger[start : start + end_match.start()] if end_match else ledger[start:]
        for line in table.splitlines():
            if not line.startswith(f"| {patch_id} |"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) == 7:
                return {
                    "impact": cells[1],
                    "reason": cells[2],
                    "alternative": cells[3],
                    "removal": cells[4],
                    "tests": cells[5],
                    "owner": "",
                    "lifecycle_status": "closed" if cells[6].startswith("**closed") else "open",
                }
            if len(cells) != 8:
                continue
            return {
                "impact": cells[1],
                "reason": cells[2],
                "alternative": cells[3],
                "removal": cells[4],
                "tests": cells[5],
                "owner": cells[6],
                "lifecycle_status": "closed" if cells[7].startswith("**closed") else "open",
            }
        return None

    section = _section(ledger, patch_id)
    if section is None:
        return None
    removal = _section_field(section, "移除条件")
    alternative = _section_field(section, "上游替代方案")
    if not alternative and removal:
        alternative = f"Adopt the upstream equivalent described by the removal condition: {removal}"
    return {
        "reason": _section_field(section, "原因"),
        "alternative": alternative,
        "impact": _section_field(section, "修改"),
        "owner": _section_field(section, "Owner"),
        "removal": removal,
        "tests": _section_field(section, "测试"),
        "lifecycle_status": "open",
    }


def _check_entry(entry: dict, ledger: str, label: str, errors: list[str]) -> None:
    patch_id = entry.get("id", label)
    metadata = _ledger_metadata(ledger, patch_id)
    if metadata is None:
        errors.append(f"{label} {patch_id}: missing detailed ledger entry")
        metadata = {}
    for field in REQUIRED_TEXT_FIELDS:
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} {patch_id}: missing {field}")
        elif _placeholder(value):
            errors.append(f"{label} {patch_id}: placeholder metadata in {field}")
    if not metadata.get("tests", "").strip():
        errors.append(f"{label} {patch_id}: missing test references")
    paths = entry.get("paths")
    if not isinstance(paths, list) or not paths:
        errors.append(f"{label} {patch_id}: paths must be a non-empty array")
        paths = []
    seen: set[str] = set()
    for path in paths:
        valid, display = _valid_path(path)
        if not valid:
            errors.append(f"{label} {patch_id}: invalid harness path {display}")
        elif path in seen:
            errors.append(f"{label} {patch_id}: duplicate path {path}")
        seen.add(display)
    status = entry.get("verification_status")
    if status not in {"historical", "current", "unexecuted", "pending"}:
        errors.append(f"{label} {patch_id}: invalid verification_status {status!r}")
    lifecycle = entry.get("lifecycle_status")
    if lifecycle not in {"open", "closed", "superseded", "archived"}:
        errors.append(f"{label} {patch_id}: invalid lifecycle_status {lifecycle!r}")
    elif metadata.get("lifecycle_status") and lifecycle != metadata["lifecycle_status"]:
        errors.append(f"{label} {patch_id}: lifecycle_status differs from the ledger entry")


def _current_evidence(entry: dict, label: str, errors: list[str]) -> None:
    patch_id = entry.get("id", label)
    if entry.get("verification_status") != "current":
        errors.append(f"{label} {patch_id}: changed patch lacks current verification status")
    evidence = entry.get("current_verification")
    if not isinstance(evidence, dict):
        errors.append(f"{label} {patch_id}: missing current verification command and result")
        return
    if not isinstance(evidence.get("command"), str) or not evidence["command"].strip():
        errors.append(f"{label} {patch_id}: missing current verification command")
    if not isinstance(evidence.get("result"), str) or not evidence["result"].strip():
        errors.append(f"{label} {patch_id}: missing current verification result")
    else:
        result = evidence["result"].lower()
        reports_failure = re.search(r"\b(?:fail(?:ed|ure)?|error|blocked|incomplete|cancelled|not run)\b", result)
        reports_success = re.search(r"\b(?:passed|pass|success|succeeded|green|ok)\b", result)
        if reports_failure or not reports_success:
            errors.append(f"{label} {patch_id}: current verification result must report success")


def _registry_paths(entries: Mapping[str, dict]) -> dict[str, list[dict]]:
    owners: dict[str, list[dict]] = {}
    for entry in entries.values():
        paths = entry.get("paths", [])
        if not isinstance(paths, list):
            continue
        for path in paths:
            if isinstance(path, str):
                owners.setdefault(path, []).append(entry)
    return owners


def check(root: Path, base: str, head: str | None, baseline: str) -> dict:
    root = root.resolve()
    base_commit = _commit(root, base, "base")
    baseline_commit = _commit(root, baseline, "upstream baseline")
    head_commit = _commit(root, head, "head") if head else None

    candidate_text = _read_ref_ledger(root, head_commit) if head_commit else _read_worktree_ledger(root)
    registry = _registry(candidate_text, "candidate")
    errors: list[str] = []
    if registry.get("schema_version") != 1:
        errors.append("candidate: unsupported registry schema_version")
    pinned_baseline = registry.get("upstream_baseline")
    if not isinstance(pinned_baseline, str):
        errors.append("candidate: missing upstream_baseline pin")
    else:
        try:
            pinned_commit = _commit(root, pinned_baseline, "ledger upstream baseline")
            if pinned_commit != baseline_commit:
                errors.append(f"baseline pin mismatch: supplied upstream baseline resolves to {baseline_commit}, ledger pins {pinned_commit}")
        except ValueError as exc:
            errors.append(str(exc))

    budget = registry.get("file_budget")
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        errors.append("candidate: file_budget must be a non-negative integer")
        budget = 0
    budget_basis = registry.get("budget_basis")
    if not isinstance(budget_basis, dict):
        errors.append("candidate: missing budget_basis")
        budget_basis = {}
    code_budget = budget_basis.get("code_files")
    document_budget = budget_basis.get("document_files")
    previous_code_budget = budget_basis.get("previous_code_files")
    previous_document_budget = budget_basis.get("previous_document_files")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (code_budget, document_budget, previous_code_budget, previous_document_budget)):
        errors.append("candidate: current and previous budget_basis counts must be non-negative integers")
        code_budget = document_budget = 0
    if code_budget + document_budget != budget:
        errors.append("candidate: file_budget must equal code_files + document_files")
    if code_budget != previous_code_budget:
        errors.append("candidate: code-file budget cannot grow in a documentation-only amendment")
    if document_budget != previous_document_budget:
        amendment = budget_basis.get("amendment")
        if not isinstance(amendment, str) or not amendment.strip():
            errors.append("candidate: document budget change requires an explicit amendment")

    entries = _entry_map(registry, "candidate", errors)
    for entry in entries.values():
        _check_entry(entry, candidate_text, "candidate", errors)
    owners = _registry_paths(entries)

    base_text = _read_ref_ledger(root, base_commit, optional=True)
    base_entries: dict[str, dict] = {}
    if base_text is not None and REGISTRY_PATTERN.search(base_text):
        try:
            base_registry = _registry(base_text, "base")
            base_entries = _entry_map(base_registry, "base", errors)
            base_basis = base_registry.get("budget_basis")
            if isinstance(base_basis, dict):
                if previous_code_budget != base_basis.get("code_files"):
                    errors.append("candidate: previous_code_files must match the base ledger allocation")
                if previous_document_budget != base_basis.get("document_files"):
                    errors.append("candidate: previous_document_files must match the base ledger allocation")
        except ValueError as exc:
            errors.append(str(exc))

    identity_changed = {
        patch_id
        for patch_id, entry in entries.items()
        if (patch_id in base_entries and entry.get("paths") != base_entries[patch_id].get("paths"))
        or (patch_id not in base_entries and base_text is None)
        or (patch_id not in base_entries and base_text is not None and _ledger_metadata(base_text, patch_id) is None)
    }
    for patch_id in sorted(identity_changed):
        _current_evidence(entries[patch_id], "new or remapped patch", errors)

    differing = _diff_paths(root, baseline_commit, head_commit)
    touched = _diff_paths(root, base_commit, head_commit)
    for path in sorted(differing):
        path_owners = owners.get(path, [])
        if not path_owners:
            errors.append(f"unregistered patch: {path}")
        if path in touched:
            for entry in path_owners:
                _current_evidence(entry, f"changed path {path}", errors)

    documents = sorted(path for path in differing if PurePosixPath(path).suffix.lower() in {".md", ".rst", ".txt"})
    code = sorted(set(differing) - set(documents))
    if len(code) > code_budget:
        errors.append(f"code patch budget exceeded: {len(code)} > {code_budget}")
    if len(documents) > document_budget:
        errors.append(f"document patch budget exceeded: {len(documents)} > {document_budget}")
    deleted = _name_set(
        git(
            root,
            "diff",
            "--no-renames",
            "--name-only",
            "-z",
            "--diff-filter=D",
            baseline_commit,
            *((head_commit,) if head_commit else ()),
            "--",
            PREFIX,
        )
    )
    if head_commit is None:
        deleted.intersection_update(differing)
    if len(differing) > budget:
        errors.append(f"patch budget exceeded: {len(differing)} > {budget}; code={len(code)} documents={len(documents)}")
    return {
        "base": base_commit,
        "head": head_commit or "working-tree",
        "upstream_baseline": baseline_commit,
        "code_files": len(code),
        "document_files": len(documents),
        "total_files": len(differing),
        "deleted_files": len(deleted),
        "file_budget": budget,
        "code_file_budget": code_budget,
        "document_file_budget": document_budget,
        "errors": errors,
        "status": "fail" if errors else "pass",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head")
    parser.add_argument("--upstream-baseline", required=True)
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        report = check(args.repo, args.base, args.head, args.upstream_baseline)
    except (ValueError, TypeError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        report = {"status": "fail", "errors": [str(exc)]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(report["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
