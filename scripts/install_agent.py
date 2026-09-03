#!/usr/bin/env python3
"""Install a bundled iDeer agent into the runtime agent directory (stdlib-only).

Generic installer for agents that are NOT covered by the canonical bundled
resource module.  The fault-zeroing Skill–Expert–Workflow dependency closure
is lifecycle-managed exclusively by the canonical bundle
(``ideer.resources.bundled`` / ``scripts/seed_bundled_resources.py``); the
legacy fault-zeroing install, subagent merge and standalone workflow seed
paths have been removed.
"""

import argparse
from datetime import datetime, timezone
import os
import re
import sqlite3
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

REQUIRED_FILES = ("config.yaml", "SOUL.md")
SAFE_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_base_dir() -> Path:
    deer_flow_home = os.environ.get("IDEER_HOME")
    if deer_flow_home:
        return Path(deer_flow_home).resolve()
    return repo_root() / "backend" / ".ideer"


def default_source_dir(agent_name: str) -> Path:
    return repo_root() / "resources" / "agents" / agent_name


def _find_super_admin_id(db_path: Path) -> str:
    try:
        with sqlite3.connect(str(db_path)) as connection:
            row = connection.execute(
                "SELECT id FROM users_ext WHERE role='super_admin' AND disabled=0 LIMIT 1"
            ).fetchone()
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"super_admin not found in {db_path}; run /initialize first"
        ) from exc

    if row is None:
        raise RuntimeError(f"super_admin not found in {db_path}; run /initialize first")
    return str(row[0])


def _upsert_agent_metadata(db_path: Path, agent_name: str, owner_id: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.execute(
                """
                INSERT INTO resource_metadata (
                    id, resource_type, resource_id, owner_id, department_id,
                    visibility, version, is_favorited, created_at, updated_at
                ) VALUES (?, 'agent', ?, ?, NULL, 'public', 1, 0, ?, ?)
                ON CONFLICT(resource_type, resource_id, owner_id)
                DO UPDATE SET visibility='public', department_id=NULL
                """,
                (uuid4().hex, agent_name, owner_id, now, now),
            )
    except sqlite3.OperationalError:
        # Older or partially migrated databases may not have this table/shape yet.
        return


def resolve_config_path() -> Path:
    config_path = os.environ.get("IDEER_CONFIG_PATH")
    if config_path:
        path = Path(config_path).resolve()
        if path.is_file():
            return path
        raise FileNotFoundError(
            f"Config file specified by IDEER_CONFIG_PATH does not exist: {path}"
        )

    for path in (repo_root() / "config.yaml", repo_root() / "backend" / "config.yaml"):
        if path.is_file():
            return path.resolve()

    raise FileNotFoundError(
        "config.yaml not found; create config.yaml before installing the bundled agent."
    )


def _validate_user_id(user_id: str) -> str:
    if not SAFE_USER_ID_RE.fullmatch(user_id):
        raise ValueError(
            "Invalid user_id: only letters, numbers, hyphens, and underscores are allowed."
        )
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
    user_id: Optional[str] = None,
    source_dir: Path,
    base_dir: Path,
) -> Tuple[Path, str]:
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
    user_id: Optional[str] = None,
    source_dir: Optional[Path] = None,
    base_dir: Optional[Path] = None,
) -> Tuple[Path, str]:
    """Copy a bundled agent into the runtime agent directory."""
    return install_agent_files(
        agent_name,
        user_id=user_id,
        source_dir=source_dir or default_source_dir(agent_name),
        base_dir=base_dir or default_base_dir(),
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install a bundled iDeer agent into the runtime agent directory."
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent name to install (resolves resources/agents/<name>/).",
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


def main(argv: Optional[list[str]] = None) -> int:
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
            _upsert_agent_metadata(
                default_base_dir() / "data" / "ideer.db", agent_name, owner_id
            )
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Agent directory: {target_dir}")
    print(f"Agent files: {file_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
