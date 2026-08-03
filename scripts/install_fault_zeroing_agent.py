#!/usr/bin/env python3
"""Install the bundled fault-zeroing agent into the runtime agent directory."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path


AGENT_NAME = "fault-zeroing"
REQUIRED_FILES = ("config.yaml", "SOUL.md")
BUNDLED_WORKFLOW_FILES = (
    "workflows/fault-zeroing.yaml",
    "skills/custom/fault-zeroing/templates/corrective_actions.schema.json",
)
SAFE_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_source_dir() -> Path:
    return repo_root() / "docs" / "fault-zeroing-agent" / "agent"


def default_base_dir() -> Path:
    if deer_flow_home := os.environ.get("IDEER_HOME"):
        return Path(deer_flow_home).resolve()
    return repo_root() / "backend" / ".ideer"


def resolve_config_path() -> Path:
    if config_path := os.environ.get("IDEER_CONFIG_PATH"):
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
        "config.yaml not found; create config.yaml before installing the fault-zeroing agent."
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
    *,
    user_id: str | None = None,
    source_dir: Path,
    base_dir: Path,
) -> tuple[Path, str]:
    """Install bundled agent files, preserving existing matching installs."""
    source = source_dir.resolve()
    runtime_base = base_dir.resolve()
    if user_id is None:
        target_dir = runtime_base / "agents" / AGENT_NAME
    else:
        safe_user_id = _validate_user_id(user_id)
        target_dir = runtime_base / "users" / safe_user_id / "agents" / AGENT_NAME

    _validate_source_dir(source)
    if target_dir.exists():
        missing = [name for name in REQUIRED_FILES if not (target_dir / name).is_file()]
        if missing:
            missing_list = ", ".join(missing)
            raise FileExistsError(
                f"Agent '{AGENT_NAME}' is partially installed at {target_dir}; missing {missing_list}. "
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
                f"Agent '{AGENT_NAME}' already exists at {target_dir} with local customizations in {mismatched_list}; "
                "refusing to overwrite."
            )
        return target_dir, "skipped"

    target_dir.mkdir(parents=True)
    for filename in REQUIRED_FILES:
        shutil.copy2(source / filename, target_dir / filename)

    return target_dir, "copied"


def install_fault_zeroing_agent(
    *,
    user_id: str | None = None,
    source_dir: Path | None = None,
    base_dir: Path | None = None,
) -> tuple[Path, str]:
    """Copy the bundled fault-zeroing agent into the runtime agent directory."""
    return install_agent_files(
        user_id=user_id,
        source_dir=source_dir or default_source_dir(),
        base_dir=base_dir or default_base_dir(),
    )


def _validate_bundled_workflow_files(repo_root_path: Path) -> None:
    """Verify bundled workflow assets ship with the release (stdlib-only)."""
    missing = [
        name for name in BUNDLED_WORKFLOW_FILES if not (repo_root_path / name).is_file()
    ]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(
            f"missing bundled workflow file(s) in {repo_root_path}: {missing_list}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the bundled fault-zeroing agent for iDeer."
    )
    parser.add_argument(
        "--user-id",
        help="Install into one iDeer user's agent directory instead of the shared directory.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        target_dir, file_status = install_fault_zeroing_agent(user_id=args.user_id)
        _validate_bundled_workflow_files(repo_root())
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Agent directory: {target_dir}")
    print(f"Agent files: {file_status}")
    print(f"Workflow files: {', '.join(BUNDLED_WORKFLOW_FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
