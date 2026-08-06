#!/usr/bin/env python3
"""Install a bundled iDeer agent into the runtime agent directory (stdlib-only)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
import re
import sqlite3
import shutil
import sys
from pathlib import Path
from uuid import uuid4

AGENT_NAME = "fault-zeroing"
REQUIRED_FILES = ("config.yaml", "SOUL.md")
REQUIRED_SUBAGENTS = [
    "evidence-reader",
    "fault-tree-builder",
    "probability-assessor",
    "root-cause-analyst",
    "report-reviewer",
]
SAFE_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def agent_docs_dir(agent_name: str) -> Path:
    return repo_root() / "docs" / f"{agent_name}-agent"


def default_source_dir(agent_name: str = AGENT_NAME) -> Path:
    return agent_docs_dir(agent_name) / "agent"


def default_subagents_file(agent_name: str = AGENT_NAME) -> Path:
    return agent_docs_dir(agent_name) / "subagents.yaml"


def default_base_dir() -> Path:
    if deer_flow_home := os.environ.get("IDEER_HOME"):
        return Path(deer_flow_home).resolve()
    return repo_root() / "backend" / ".ideer"


def _find_super_admin_id(db_path: Path) -> str:
    try:
        with sqlite3.connect(db_path) as connection:
            row = connection.execute(
                "SELECT id FROM users_ext WHERE role='super_admin' AND disabled=0 LIMIT 1"
            ).fetchone()
    except sqlite3.Error as exc:
        raise RuntimeError(f"super_admin not found in {db_path}; run /initialize first") from exc

    if row is None:
        raise RuntimeError(f"super_admin not found in {db_path}; run /initialize first")
    return str(row[0])


def _upsert_agent_metadata(db_path: Path, agent_name: str, owner_id: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                INSERT INTO resource_metadata (
                    id, resource_type, resource_id, owner_id, department_id,
                    visibility, version, is_favorited, created_at, updated_at
                ) VALUES (?, 'agent', ?, ?, NULL, 'private', 1, 0, ?, ?)
                ON CONFLICT(resource_type, resource_id, owner_id)
                DO UPDATE SET visibility='private', department_id=NULL
                """,
                (uuid4().hex, agent_name, owner_id, now, now),
            )
    except sqlite3.OperationalError:
        # Older or partially migrated databases may not have this table/shape yet.
        return


def resolve_config_path() -> Path:
    if config_path := os.environ.get("IDEER_CONFIG_PATH"):
        path = Path(config_path).resolve()
        if path.is_file():
            return path
        raise FileNotFoundError(f"Config file specified by IDEER_CONFIG_PATH does not exist: {path}")

    for path in (repo_root() / "config.yaml", repo_root() / "backend" / "config.yaml"):
        if path.is_file():
            return path.resolve()

    raise FileNotFoundError(
        "config.yaml not found; create config.yaml before installing the bundled agent."
    )


def _validate_user_id(user_id: str) -> str:
    if not SAFE_USER_ID_RE.fullmatch(user_id):
        raise ValueError("Invalid user_id: only letters, numbers, hyphens, and underscores are allowed.")
    return user_id


def _validate_source_dir(source_dir: Path) -> None:
    missing = [name for name in REQUIRED_FILES if not (source_dir / name).is_file()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(
            f"Missing required agent file(s) in {source_dir}: {missing_list}"
        )


def files_match(source: Path, target: Path) -> bool:
    return source.read_bytes() == target.read_bytes()


def install_agent_files(
    agent_name: str,
    *,
    user_id: str | None = None,
    source_dir: Path,
    base_dir: Path,
) -> tuple[Path, str]:
    """Install bundled agent files, preserving existing matching installs."""
    source = source_dir.resolve()
    runtime_base = base_dir.resolve()
    if user_id is None:
        target_dir = runtime_base / "agents" / agent_name
    else:
        safe_user_id = _validate_user_id(user_id)
        target_dir = runtime_base / "users" / safe_user_id / "agents" / agent_name

    _validate_source_dir(source)
    if target_dir.exists():
        missing = [name for name in REQUIRED_FILES if not (target_dir / name).is_file()]
        if missing:
            missing_list = ", ".join(missing)
            raise FileExistsError(
                f"Agent '{agent_name}' is partially installed at {target_dir}; missing {missing_list}. "
                "Fix or remove the directory manually before reinstalling."
            )
        mismatched = [
            name
            for name in REQUIRED_FILES
            if not files_match(source / name, target_dir / name)
        ]
        if mismatched:
            mismatched_list = ", ".join(mismatched)
            raise FileExistsError(
                f"Agent '{agent_name}' already exists at {target_dir} with local customizations in {mismatched_list}; "
                "refusing to overwrite."
            )
        return target_dir, "skipped"

    target_dir.mkdir(parents=True)
    for filename in REQUIRED_FILES:
        shutil.copy2(source / filename, target_dir / filename)

    return target_dir, "copied"


def install_agent(
    *,
    agent_name: str,
    user_id: str | None = None,
    source_dir: Path | None = None,
    base_dir: Path | None = None,
) -> tuple[Path, str]:
    """Copy a bundled agent into the runtime agent directory."""
    return install_agent_files(
        agent_name,
        user_id=user_id,
        source_dir=source_dir or default_source_dir(agent_name),
        base_dir=base_dir or default_base_dir(),
    )


def install_fault_zeroing_agent(
    *,
    user_id: str | None = None,
    source_dir: Path | None = None,
    base_dir: Path | None = None,
) -> tuple[Path, str]:
    """Copy the bundled fault-zeroing agent into the runtime agent directory."""
    return install_agent(
        agent_name=AGENT_NAME,
        user_id=user_id,
        source_dir=source_dir,
        base_dir=base_dir,
    )


def _extract_agent_blocks(subagents_file: Path) -> dict[str, list[str]]:
    lines = subagents_file.read_text(encoding="utf-8").splitlines(keepends=True)
    blocks: dict[str, list[str]] = {}
    index = 0
    while index < len(lines):
        match = re.match(r"^    ([A-Za-z0-9_-]+):\s*$", lines[index])
        if not match:
            index += 1
            continue

        name = match.group(1)
        start = index
        index += 1
        while index < len(lines) and not re.match(r"^    [A-Za-z0-9_-]+:\s*$", lines[index]):
            index += 1
        blocks[name] = lines[start:index]

    missing = [name for name in REQUIRED_SUBAGENTS if name not in blocks]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"subagents.yaml is missing required custom subagent(s): {missing_list}")
    return {name: blocks[name] for name in REQUIRED_SUBAGENTS}


def _has_subagent(lines: list[str], name: str) -> bool:
    pattern = re.compile(rf"^    {re.escape(name)}:\s*$")
    return any(pattern.match(line) for line in lines)


def _subagent_description(lines: list[str], name: str) -> str | None:
    pattern = re.compile(rf"^    {re.escape(name)}:\s*$")
    start: int | None = None
    for index, line in enumerate(lines):
        if pattern.match(line):
            start = index
            break
    if start is None:
        return None

    for line in lines[start + 1 :]:
        if re.match(r"^    [A-Za-z0-9_-]+:\s*$", line):
            return None
        match = re.match(r"^\s+description:\s*(.*)\s*$", line)
        if match:
            return match.group(1).strip("'\"")
    return None


def _find_top_level_block(lines: list[str], key: str) -> tuple[int | None, int]:
    start: int | None = None
    end = len(lines)
    for index, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}:\s*$", line):
            start = index
            continue
        if start is not None and index > start and re.match(r"^[A-Za-z0-9_-]+:", line):
            end = index
            break
    return start, end


def _find_custom_agents_line(lines: list[str], start: int, end: int) -> int | None:
    for index in range(start + 1, end):
        if re.match(r"^  custom_agents:\s*$", lines[index]):
            return index
    return None


def _find_custom_agents_end(lines: list[str], start: int, end: int) -> int:
    index = start + 1
    while index < end:
        line = lines[index]
        if line.strip() and not line.startswith("    "):
            break
        index += 1
    return index


def merge_fault_zeroing_subagents(config_path: Path, subagents_file: Path) -> dict:
    config_path = config_path.resolve()
    subagents_file = subagents_file.resolve()
    source_blocks = _extract_agent_blocks(subagents_file)
    config_text = config_path.read_text(encoding="utf-8")
    lines = [] if config_text.strip() in {"", "{}", "null"} else config_text.splitlines(keepends=True)

    added: list[str] = []
    skipped: list[str] = []
    for name in REQUIRED_SUBAGENTS:
        if _has_subagent(lines, name):
            source_description = _subagent_description(source_blocks[name], name)
            target_description = _subagent_description(lines, name)
            if source_description and target_description and source_description != target_description:
                raise ValueError(
                    f"Conflicting custom subagent definition(s) in {config_path}: {name}"
                )
            skipped.append(name)
        else:
            added.append(name)

    summary = {
        "added": added,
        "skipped": skipped,
        "config_path": config_path,
    }
    if not added:
        return summary

    backup_path = config_path.with_name(f"{config_path.name}.bak-fault-zeroing")
    shutil.copy2(config_path, backup_path)
    insert_lines = [line for name in REQUIRED_SUBAGENTS for line in source_blocks[name]]
    subagents_start, subagents_end = _find_top_level_block(lines, "subagents")
    if subagents_start is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] = f"{lines[-1]}\n"
        lines.extend(["subagents:\n", "  custom_agents:\n", *insert_lines])
    else:
        custom_agents_index = _find_custom_agents_line(lines, subagents_start, subagents_end)
        if custom_agents_index is None:
            lines[subagents_start + 1 : subagents_start + 1] = ["  custom_agents:\n", *insert_lines]
        else:
            custom_agents_end = _find_custom_agents_end(lines, custom_agents_index, subagents_end)
            lines[custom_agents_end:custom_agents_end] = insert_lines
    config_path.write_text("".join(lines), encoding="utf-8")
    summary["backup_path"] = backup_path
    return summary


def validate_fault_zeroing_subagent_registry(config_path: Path) -> list[str]:
    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    missing = [name for name in REQUIRED_SUBAGENTS if not _has_subagent(lines, name)]
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(f"Fault-zeroing custom subagent config check failed; missing: {missing_list}")
    return REQUIRED_SUBAGENTS.copy()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install a bundled iDeer agent (default: fault-zeroing).")
    parser.add_argument(
        "--agent",
        default=AGENT_NAME,
        help="Agent name to install (resolves docs/<name>-agent/agent and docs/<name>-agent/subagents.yaml).",
    )
    owner_group = parser.add_mutually_exclusive_group()
    owner_group.add_argument(
        "--user-id",
        help="Install into one iDeer user's agent directory instead of the shared directory.",
    )
    owner_group.add_argument(
        "--owner",
        choices=("super-admin",),
        help="Install for the active super_admin from the local database.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    agent_name = args.agent
    try:
        owner_id = None
        if args.owner == "super-admin":
            owner_id = _find_super_admin_id(default_base_dir() / "data" / "ideer.db")
        target_dir, file_status = install_agent(
            agent_name=agent_name,
            user_id=owner_id or args.user_id,
        )
        if owner_id:
            _upsert_agent_metadata(default_base_dir() / "data" / "ideer.db", agent_name, owner_id)
        subagents_file = default_subagents_file(agent_name)
        if not subagents_file.is_file():
            print(f"Agent directory: {target_dir}")
            print(f"Agent files: {file_status}")
            print(f"Subagents: (none - no bundled subagents.yaml for {agent_name})")
            return 0
        config_path = resolve_config_path()
        merge_summary = merge_fault_zeroing_subagents(config_path, subagents_file)
        verified_subagents = validate_fault_zeroing_subagent_registry(config_path)
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Agent directory: {target_dir}")
    print(f"Agent files: {file_status}")
    print(f"Config path: {merge_summary['config_path']}")
    if backup_path := merge_summary.get("backup_path"):
        print(f"Config backup: {backup_path}")
    print(f"Subagents added: {', '.join(merge_summary['added']) or '(none)'}")
    print(f"Subagents skipped: {', '.join(merge_summary['skipped']) or '(none)'}")
    print(f"Registry check passed: {', '.join(verified_subagents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
