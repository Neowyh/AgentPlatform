#!/usr/bin/env python3
"""One-shot installer for the bundled SRS 撰写 (需求规格) agent.

Composes the generic ``install_agent`` flow with the functional wiring the
agent needs on a local (host-sandbox) deployment:

  1. Install agent files (docs/srs-writing-agent/agent) into the runtime
     per-user agent directory and upsert resource_metadata (agent/private).
  2. Register the ``document`` tool group and ``read_document`` tool in
     config.yaml so docx/pdf 任务书 can be parsed.
  3. Set ``sandbox.allow_host_bash: true`` (explicit opt-in) so officecli can
     generate .docx artifacts inside the sandbox.
  4. Provision an officecli binary on PATH (symlink into ~/.local/bin) so the
     tracked vendor binary is reachable without sudo.

Stdlib-only, idempotent, and safe to re-run: existing matching installs are
preserved, config edits are applied once (a config backup is made before the
first change), and the officecli symlink never overwrites an unrelated file
unless ``--force`` is given.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

from install_agent import _find_super_admin_id, _find_top_level_block, default_base_dir, resolve_config_path
from install_agent import main as install_agent_main

SRS_AGENT = "srs-writing"
READ_DOCUMENT_USE = "ideer.community.doc_reader.tools:read_document_tool"
APP_CONFIG_BACKUP_SUFFIX = ".bak-before-srs-agent"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def bundled_officecli() -> Path:
    return repo_root() / "vendor" / "officecli" / "officecli"


def default_officecli_bin() -> Path:
    return Path.home() / ".local" / "bin" / "officecli"


def _same_file_content(first: Path, second: Path) -> bool:
    if not first.is_file() or not second.is_file():
        return False
    digest = hashlib.sha256()
    try:
        with first.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        first_digest = digest.digest()
        digest = hashlib.sha256()
        with second.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return first_digest == digest.digest()
    except OSError:
        return False


def resolve_owner_id(args: argparse.Namespace) -> tuple[str | None, str]:
    """Return ``(owner_id, install_style)`` with style ``super-admin``/``user``/``shared``."""
    if args.owner == "super-admin":
        db_path = default_base_dir() / "data" / "ideer.db"
        try:
            return _find_super_admin_id(db_path), "super-admin"
        except RuntimeError as exc:
            raise RuntimeError(f"{exc}; run /initialize first or use --user-id to install for a specific user.") from exc
    if args.user_id:
        return args.user_id, "user"
    return None, "shared"


def expected_agent_dir(owner_id: str | None) -> Path:
    base = Path(default_base_dir())
    if owner_id is None:
        return base / "agents" / SRS_AGENT
    return base / "users" / owner_id / "agents" / SRS_AGENT


def _has_document_tool_group(lines: list[str]) -> bool:
    return any(re.match(r"^\s*- name: document\s*$", line) for line in lines)


def _has_read_document_tool(lines: list[str]) -> bool:
    return any(re.match(r"^\s*- name: read_document\s*$", line) for line in lines)


def _set_allow_host_bash(lines: list[str], value: bool) -> list[str]:
    new_line = f"  allow_host_bash: {str(value).lower()}\n"
    start, end = _find_top_level_block(lines, "sandbox")
    if start is None:
        lines.append("sandbox:\n")
        lines.append(new_line)
        return lines
    for index in range(start + 1, end):
        match = re.match(r"^(\s*allow_host_bash:)\s*\S*.*$", lines[index])
        if match:
            lines[index] = f"{match.group(1)} {str(value).lower()}\n"
            return lines
    lines.insert(start + 1, new_line)
    return lines


def allow_host_bash_value(lines: list[str]) -> bool | None:
    start, end = _find_top_level_block(lines, "sandbox")
    if start is None:
        return None
    for line in lines[start + 1 : end]:
        match = re.match(r"^\s*allow_host_bash:\s*(\S+)", line)
        if match:
            return match.group(1).lower().startswith("t")
    return None


def _list_indent(lines: list[str], start: int, end: int) -> str:
    """Indentation (whitespace prefix) of the first ``- item`` in a block.

    Defaults to two spaces so inserts stay valid YAML even when the block has
    no items yet. Real config templates indent lists under a top-level key.
    """
    for line in lines[start + 1 : end]:
        match = re.match(r"^([ \t]*)- ", line)
        if match:
            return match.group(1)
    return "  "


def _add_document_tool_group(lines: list[str]) -> list[str]:
    start, end = _find_top_level_block(lines, "tool_groups")
    indent = _list_indent(lines, start, end) if start is not None else "  "
    if start is None:
        lines.append("tool_groups:\n")
        lines.append(f"{indent}- name: document\n")
        return lines
    last = start
    for index in range(start + 1, end):
        if re.match(r"^\s*- name: \S+", lines[index]):
            last = index
    lines.insert(last + 1, f"{indent}- name: document\n")
    return lines


def _add_read_document_tool(lines: list[str]) -> list[str]:
    start, end = _find_top_level_block(lines, "tools")
    indent = _list_indent(lines, start, end) if start is not None else "  "
    block = [
        f"{indent}- name: read_document\n",
        f"{indent}  group: document\n",
        f"{indent}  use: {READ_DOCUMENT_USE}\n",
    ]
    if start is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] = f"{lines[-1]}\n"
        lines.append("tools:\n")
        lines.extend(block)
        return lines
    lines[end:end] = block
    return lines


def wire_srs_config(
    config_path: str | Path,
    *,
    enable_doc_tools: bool = True,
    enable_host_bash: bool = True,
    dry_run: bool = False,
) -> dict:
    """Register SRS agent prerequisites in ``config.yaml`` (idempotent).

    Returns ``{config_path, actions, changed, backup_path}``. In dry-run mode
    nothing is written.
    """
    config_path = Path(config_path)
    original = config_path.read_text(encoding="utf-8")
    lines: list[str] = []
    if original.strip() not in {"", "{}", "null"}:
        lines = original.splitlines(keepends=True)

    actions: dict[str, str] = {}
    if enable_doc_tools:
        if _has_document_tool_group(lines):
            actions["document_tool_group"] = "present"
        else:
            lines = _add_document_tool_group(lines)
            actions["document_tool_group"] = "added"
        if _has_read_document_tool(lines):
            actions["read_document_tool"] = "present"
        else:
            lines = _add_read_document_tool(lines)
            actions["read_document_tool"] = "added"

    if enable_host_bash:
        current = allow_host_bash_value(lines)
        if current is True:
            actions["allow_host_bash"] = "present"
        else:
            lines = _set_allow_host_bash(lines, True)
            actions["allow_host_bash"] = "added" if current is None else "changed"

    changed = any(state != "present" for state in actions.values())
    backup_path = config_path.with_name(f"{config_path.name}{APP_CONFIG_BACKUP_SUFFIX}")
    if changed and not dry_run:
        if not backup_path.is_file():
            shutil.copy2(config_path, backup_path)
        config_path.write_text("".join(lines), encoding="utf-8")
    elif changed and dry_run:
        pass  # report only

    return {
        "config_path": str(config_path),
        "actions": actions,
        "changed": changed,
        "backup_path": str(backup_path) if backup_path.is_file() else None,
    }


def provision_officecli(
    repo_root_path: str | Path,
    *,
    bin_path: str | Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    """Symlink the bundled officecli binary onto PATH (~/.local/bin)."""
    source = Path(repo_root_path) / "vendor" / "officecli" / "officecli"
    destination = Path(bin_path) if bin_path else default_officecli_bin()
    if not source.is_file():
        return {"status": "missing_source", "source": str(source), "bin": str(destination)}

    if destination.is_symlink() and destination.resolve() == source.resolve():
        return {"status": "linked", "source": str(source), "bin": str(destination)}
    if destination.exists():
        if _same_file_content(destination, source):
            return {"status": "equivalent", "source": str(source), "bin": str(destination)}
        if not force:
            return {"status": "conflict", "source": str(source), "bin": str(destination)}
        if dry_run:
            return {"status": "will_replace", "source": str(source), "bin": str(destination)}
        destination.unlink()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(source)
        return {"status": "replaced", "source": str(source), "bin": str(destination)}
    if dry_run:
        return {"status": "will_create", "source": str(source), "bin": str(destination)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source)
    return {"status": "created", "source": str(source), "bin": str(destination)}


def yaml_parse_ok(path: Path) -> bool:
    """Best-effort YAML validity check via an isolated subprocess (keeps this
    script standard-library only). Hosts without a ``yaml`` module installed
    cannot verify, so the check passes rather than hard-failing the installer.
    """
    if importlib.util.find_spec("yaml") is None:
        return True
    code = "import sys; import yaml\ntry:\n    with open(sys.argv[1], encoding='utf-8') as fh:\n        yaml.safe_load(fh)\nexcept Exception:\n    sys.exit(1)\n"
    try:
        result = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, timeout=60)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def officecli_available(bin_path: Path, *, bundled: Path | None = None) -> bool:
    reference = bundled if bundled is not None else bundled_officecli()
    if bin_path.is_symlink():
        try:
            if bin_path.resolve() == reference.resolve():
                return True
        except OSError:
            return False
    return _same_file_content(bin_path, reference)


def verify_install(
    config_path: str | Path,
    *,
    owner_id: str | None,
    bin_path: str | Path | None = None,
    require_officecli: bool = True,
) -> dict:
    """Inspect the current runtime state and report what is present.

    ``require_officecli=False`` marks the officecli check as not applicable
    (partial installs with ``--no-officecli``).
    """
    config_path = Path(config_path)
    agent_dir = expected_agent_dir(owner_id)
    agent_config = agent_dir / "config.yaml"
    agent_soul = agent_dir / "SOUL.md"
    config_lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    officecli = Path(bin_path) if bin_path else default_officecli_bin()

    checks = {
        "agent_files": agent_config.is_file() and agent_soul.is_file(),
        "config_yaml": yaml_parse_ok(config_path),
        "document_group": _has_document_tool_group(config_lines),
        "read_document_tool": _has_read_document_tool(config_lines),
        "allow_host_bash": allow_host_bash_value(config_lines) is True,
        "officecli": officecli_available(officecli) if require_officecli else True,
    }
    return {
        "checks": checks,
        "agent_dir": str(agent_dir),
        "config_path": str(config_path),
        "officecli_bin": str(officecli),
    }


def print_verify_report(report: dict) -> None:
    print(f"Agent directory : {report['agent_dir']}")
    print(f"Config          : {report['config_path']}")
    print(f"officecli       : {report['officecli_bin']}")
    for key in (
        "agent_files",
        "config_yaml",
        "document_group",
        "read_document_tool",
        "allow_host_bash",
        "officecli",
    ):
        status = report["checks"][key]
        print(f"  - {key:.<20} {'OK' if status else 'MISSING'}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the bundled SRS 撰写智能体 (srs-writing) end-to-end (agent files + read_document tool + host bash + officecli).",
    )
    parser.add_argument("--agent", default=SRS_AGENT, help="Bundled agent name to install.")
    owner = parser.add_mutually_exclusive_group()
    owner.add_argument("--owner", choices=("super-admin",), help="Install as the active super_admin.")
    owner.add_argument("--user-id", help="Install into this iDeer user's agent directory.")
    parser.add_argument("--skip-agent", action="store_true", help="Only wire config/officecli (skip the agent file install).")
    parser.add_argument("--no-doc-tools", action="store_true", help="Do not register the document/read_document tool.")
    parser.add_argument("--no-host-bash", action="store_true", help="Do not enable sandbox.allow_host_bash.")
    parser.add_argument("--no-officecli", action="store_true", help="Do not provision the officecli binary.")
    parser.add_argument("--force", action="store_true", help="Overwrite a conflicting ~/.local/bin/officecli.")
    parser.add_argument("--dry-run", action="store_true", help="Report planned changes without writing.")
    parser.add_argument("--verify-only", action="store_true", help="Only inspect the current state.")
    parser.add_argument("--restart", action="store_true", help="Restart local services after a successful install.")
    return parser.parse_args(argv)


def _print_config_summary(wire: dict, officecli_status: str | None) -> None:
    for item, state in wire["actions"].items():
        print(f"Config : {item:24s} {state}")
    if wire["changed"]:
        print(f"Config backup   : {wire['backup_path']}")
    if officecli_status is not None:
        print(f"officecli       : {officecli_status}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.owner:
        owner_id, install_style = resolve_owner_id(args)
    elif args.user_id:
        owner_id, install_style = args.user_id, "user"
    else:
        owner_id, install_style = None, "shared"

    config_path = Path(resolve_config_path())

    want_doc = not args.no_doc_tools
    want_host_bash = not args.no_host_bash
    want_officecli = not args.no_officecli

    if args.verify_only:
        report = verify_install(config_path, owner_id=owner_id, require_officecli=want_officecli)
        print_verify_report(report)
        return 0 if all(report["checks"].values()) else 1

    print(f"== Installer target: '{args.agent}' for owner={install_style}")
    print(f"   runtime base   : {default_base_dir()}")

    if args.dry_run:
        print("== Dry run (no changes are written)")
        if not args.skip_agent:
            print(f"   - copy agent files -> {expected_agent_dir(owner_id)}")
        if want_doc:
            print("   - register document tool group + read_document tool in config.yaml")
        if want_host_bash:
            print("   - set sandbox.allow_host_bash = true")
        if want_officecli:
            print(f"   - symlink officecli -> {default_officecli_bin()}")
        return 0

    if not args.skip_agent:
        agent_args = ["--agent", args.agent]
        if install_style == "super-admin":
            agent_args += ["--owner", "super-admin"]
        elif install_style == "user":
            agent_args += ["--user-id", args.user_id]
        code = install_agent_main(agent_args)
        if code != 0:
            return code
    else:
        print("   agent: skipped (--skip-agent)")

    wire = wire_srs_config(
        config_path,
        enable_doc_tools=want_doc,
        enable_host_bash=want_host_bash,
    )

    officecli_status: str | None = None
    if want_officecli:
        result = provision_officecli(repo_root(), force=args.force)
        officecli_status = result["status"]
        if officecli_status == "conflict":
            print(f"Error: {result['bin']} already exists and is not the bundled officecli. Use --force to overwrite it.", file=sys.stderr)
            return 1

    _print_config_summary(wire, officecli_status)

    report = verify_install(config_path, owner_id=owner_id, require_officecli=want_officecli)
    print_verify_report(report)

    ok = all(report["checks"].values())
    if not ok:
        print("Some checks are incomplete; review the MISSING items above.", file=sys.stderr)
    elif args.restart:
        restart_command = repo_root() / "scripts" / "run-local-services.sh"
        if restart_command.is_file():
            print("== Restarting local services (per --restart)")
            subprocess.run([str(restart_command), "restart"], check=False)
        else:
            print("--restart requested but scripts/run-local-services.sh is missing.", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
