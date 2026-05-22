#!/usr/bin/env python3
"""Install the bundled fault-zeroing agent into a user's runtime directory."""

from __future__ import annotations

import argparse
import importlib
import os
import re
import shutil
import sys
import types
from pathlib import Path

import yaml


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


def default_source_dir() -> Path:
    return repo_root() / "docs" / "fault-zeroing-agent" / "agent"


def default_subagents_file() -> Path:
    return repo_root() / "docs" / "fault-zeroing-agent" / "subagents.yaml"


def default_base_dir() -> Path:
    if deer_flow_home := os.environ.get("DEER_FLOW_HOME"):
        return Path(deer_flow_home).resolve()
    return repo_root() / "backend" / ".deer-flow"


def resolve_config_path() -> Path:
    if config_path := os.environ.get("DEER_FLOW_CONFIG_PATH"):
        path = Path(config_path).resolve()
        if path.is_file():
            return path
        raise FileNotFoundError(f"Config file specified by DEER_FLOW_CONFIG_PATH does not exist: {path}")

    for path in (repo_root() / "config.yaml", repo_root() / "backend" / "config.yaml"):
        if path.is_file():
            return path.resolve()

    raise FileNotFoundError("config.yaml not found; create config.yaml before installing the fault-zeroing agent.")


def _validate_user_id(user_id: str) -> str:
    if not SAFE_USER_ID_RE.fullmatch(user_id):
        raise ValueError("Invalid user_id: only letters, numbers, hyphens, and underscores are allowed.")
    return user_id


def _validate_source_dir(source_dir: Path) -> None:
    missing = [name for name in REQUIRED_FILES if not (source_dir / name).is_file()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Missing required agent file(s) in {source_dir}: {missing_list}")


def files_match(source: Path, target: Path) -> bool:
    return source.read_bytes() == target.read_bytes()


def install_agent_files(
    *,
    user_id: str,
    source_dir: Path,
    base_dir: Path,
) -> tuple[Path, str]:
    """Install bundled agent files, preserving existing matching installs."""
    safe_user_id = _validate_user_id(user_id)
    source = source_dir.resolve()
    runtime_base = base_dir.resolve()
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
        mismatched = [name for name in REQUIRED_FILES if not files_match(source / name, target_dir / name)]
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
    user_id: str,
    source_dir: Path | None = None,
    base_dir: Path | None = None,
) -> tuple[Path, str]:
    """Copy the bundled fault-zeroing agent into the given user's agent directory."""
    return install_agent_files(
        user_id=user_id,
        source_dir=source_dir or default_source_dir(),
        base_dir=base_dir or default_base_dir(),
    )


def load_yaml_mapping(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a mapping: {path}")
    return data


def _load_source_custom_agents(subagents_file: Path) -> dict:
    source_data = load_yaml_mapping(subagents_file)
    subagents = source_data.get("subagents")
    if not isinstance(subagents, dict):
        raise ValueError(f"subagents.yaml must contain subagents mapping: {subagents_file}")
    custom_agents = subagents.get("custom_agents")
    if not isinstance(custom_agents, dict):
        raise ValueError(f"subagents.yaml must contain subagents.custom_agents mapping: {subagents_file}")

    missing = [name for name in REQUIRED_SUBAGENTS if name not in custom_agents]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"subagents.yaml is missing required custom subagent(s): {missing_list}")
    return {name: custom_agents[name] for name in REQUIRED_SUBAGENTS}


def merge_fault_zeroing_subagents(config_path: Path, subagents_file: Path) -> dict:
    config_path = config_path.resolve()
    subagents_file = subagents_file.resolve()
    config_data = load_yaml_mapping(config_path)
    source_custom_agents = _load_source_custom_agents(subagents_file)

    subagents = config_data.setdefault("subagents", {})
    if not isinstance(subagents, dict):
        raise ValueError(f"{config_path} field subagents must be a mapping.")

    target_custom_agents = subagents.setdefault("custom_agents", {})
    if not isinstance(target_custom_agents, dict):
        raise ValueError(f"{config_path} field subagents.custom_agents must be a mapping.")

    added: list[str] = []
    skipped: list[str] = []
    conflicts: list[str] = []
    for name, source_config in source_custom_agents.items():
        if name not in target_custom_agents:
            added.append(name)
        elif target_custom_agents[name] == source_config:
            skipped.append(name)
        else:
            conflicts.append(name)

    if conflicts:
        conflicts_list = ", ".join(conflicts)
        raise ValueError(f"Conflicting custom subagent definition(s) in {config_path}: {conflicts_list}")

    summary = {
        "added": added,
        "skipped": skipped,
        "config_path": config_path,
    }
    if not added:
        return summary

    backup_path = config_path.with_name(f"{config_path.name}.bak-fault-zeroing")
    shutil.copy2(config_path, backup_path)
    for name in added:
        target_custom_agents[name] = source_custom_agents[name]
    config_path.write_text(yaml.safe_dump(config_data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    summary["backup_path"] = backup_path
    return summary


def validate_fault_zeroing_subagent_registry(config_path: Path) -> list[str]:
    harness_path = repo_root() / "backend" / "packages" / "harness"
    sys.path.insert(0, str(harness_path.resolve()))
    subagents_package_name = "deerflow.subagents"
    if subagents_package_name not in sys.modules:
        subagents_package = types.ModuleType(subagents_package_name)
        subagents_package.__path__ = [str(harness_path / "deerflow" / "subagents")]
        sys.modules[subagents_package_name] = subagents_package

    previous_config_path = os.environ.get("DEER_FLOW_CONFIG_PATH")
    os.environ["DEER_FLOW_CONFIG_PATH"] = str(config_path.resolve())
    try:
        from deerflow.config.app_config import reload_app_config

        registry = importlib.import_module("deerflow.subagents.registry")
        app_config = reload_app_config(str(config_path))
        missing = [
            name
            for name in REQUIRED_SUBAGENTS
            if registry.get_subagent_config(name, app_config=app_config) is None
        ]
        if missing:
            missing_list = ", ".join(missing)
            raise RuntimeError(f"Fault-zeroing custom subagent registry check failed; missing: {missing_list}")
        return REQUIRED_SUBAGENTS.copy()
    finally:
        if previous_config_path is None:
            os.environ.pop("DEER_FLOW_CONFIG_PATH", None)
        else:
            os.environ["DEER_FLOW_CONFIG_PATH"] = previous_config_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install the bundled fault-zeroing agent for one DeerFlow user.")
    parser.add_argument("--user-id", required=True, help="Target DeerFlow user ID.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        target_dir, file_status = install_fault_zeroing_agent(user_id=args.user_id)
        config_path = resolve_config_path()
        merge_summary = merge_fault_zeroing_subagents(config_path, default_subagents_file())
        verified_subagents = validate_fault_zeroing_subagent_registry(config_path)
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError, yaml.YAMLError) as exc:
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
