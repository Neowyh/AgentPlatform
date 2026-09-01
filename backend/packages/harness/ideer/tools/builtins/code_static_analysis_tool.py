"""Fixed, offline C static-analysis capability for Code Evidence Packages."""

from __future__ import annotations

import json
import subprocess

from langchain.tools import tool

from ideer.config.paths import get_paths
from ideer.runtime.user_context import get_effective_user_id
from ideer.tools.types import Runtime
from ideer.uploads.code_analysis import SCANNER_TIMEOUT_SECONDS, fixed_scanner_commands, inventory_package, normalize_scanner_output, run_fixed_scanner, write_analysis_summary
from ideer.uploads.code_evidence import package_root


@tool("analyze_code_evidence", parse_docstring=True)
def analyze_code_evidence(runtime: Runtime) -> str:
    """Run the preinstalled fixed C analyzer profile for the current code package.

    The package and output directories come from authenticated run context. No
    path, executable, flags, build, or execution request is accepted from the
    model.
    """
    context = runtime.context or {}
    thread_id = context.get("thread_id")
    package_id = context.get("code_package_id")
    if not isinstance(thread_id, str) or not isinstance(package_id, str):
        return json.dumps({"error": "analyze_code_evidence requires code mode package context"})
    root = package_root(thread_id, package_id)
    if not root.is_dir():
        return json.dumps({"error": "Code Evidence Package is unavailable"})
    output = get_paths().sandbox_outputs_dir(thread_id, user_id=get_effective_user_id()) / "artifacts" / "code-analysis"
    inventory = inventory_package(root)
    findings = []
    scanners = []
    for name, command in fixed_scanner_commands(root, output):
        version = "unavailable"
        version_command = [command[0], "--version"]
        try:
            version_result = subprocess.run(version_command, capture_output=True, text=True, shell=False, check=False, timeout=SCANNER_TIMEOUT_SECONDS)
            if version_result.stdout:
                version = version_result.stdout.splitlines()[0].strip()
        except subprocess.TimeoutExpired:
            version = f"timeout after {SCANNER_TIMEOUT_SECONDS} seconds"
        raw_path = output / f"{name}.raw.txt"
        return_code, _raw = run_fixed_scanner(command, cwd=root / "source", output_file=raw_path)
        scanners.append({"name": name, "version": version, "command": [command[0]], "return_code": return_code, "raw_artifact": str(raw_path)})
        findings.extend(normalize_scanner_output(name, version, _raw, source_root=root / "source"))
    write_analysis_summary(output, inventory, findings)
    return json.dumps({"inventory": inventory, "scanners": scanners, "findings_artifact": str(output / "findings.json")}, ensure_ascii=False)
