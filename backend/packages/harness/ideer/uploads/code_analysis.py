"""Deterministic, read-only evidence extraction for C packages."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

EvidenceMode = Literal["document", "code", "hybrid"]
FindingConfidence = Literal["confirmed", "high_risk_candidate", "pending_verification"]

_SOURCE_SUFFIXES = {".c", ".h", ".cc", ".cpp", ".cxx"}
_LOG_SUFFIXES = {".log", ".txt", ".md"}


@dataclass(frozen=True)
class StaticFinding:
    scanner: str
    version: str
    rule_id: str
    path: str
    line: int | None
    message: str
    confidence: FindingConfidence = "high_risk_candidate"

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def inventory_package(package_root: Path) -> dict:
    """Inventory only regular files below the validated package source root."""
    source_root = package_root / "source"
    files: list[str] = []
    source_files: list[str] = []
    headers: list[str] = []
    logs: list[str] = []
    build_metadata: list[str] = []
    if source_root.is_dir():
        for path in sorted(source_root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(source_root).as_posix()
            files.append(relative)
            suffix = path.suffix.lower()
            if suffix in _SOURCE_SUFFIXES:
                source_files.append(relative)
            if suffix == ".h":
                headers.append(relative)
            if suffix in _LOG_SUFFIXES or path.name.lower() in {"fault.log", "error.log"}:
                logs.append(relative)
            if path.name in {"compile_commands.json", "CMakeLists.txt", "Makefile"}:
                build_metadata.append(relative)
    return {
        "files": files,
        "source_files": source_files,
        "headers": headers,
        "logs": logs,
        "build_metadata": build_metadata,
        "compilation_configuration_verified": "compile_commands.json" in {Path(item).name for item in build_metadata},
    }


def confidence_for_finding(*, has_correlated_context: bool, is_static_alert: bool = True) -> FindingConfidence:
    """Apply the report contract: an alert alone is never confirmed."""
    if has_correlated_context and not is_static_alert:
        return "confirmed"
    if has_correlated_context:
        return "high_risk_candidate"
    return "high_risk_candidate" if is_static_alert else "pending_verification"


def fixed_scanner_commands(package_root: Path, output_dir: Path) -> list[tuple[str, list[str]]]:
    """Return fixed scanner invocations; caller must execute without a shell."""
    source = package_root / "source"
    output_dir.mkdir(parents=True, exist_ok=True)
    commands: list[tuple[str, list[str]]] = []
    if shutil.which("clang-tidy"):
        commands.append(("clang-tidy", ["clang-tidy", "--quiet", "-p", str(source), "--", "-fsyntax-only"]))
    if shutil.which("cppcheck"):
        commands.append(("cppcheck", ["cppcheck", "--enable=warning,style,performance,portability", "--xml", "--xml-version=2", str(source)]))
    return commands


def run_fixed_scanner(command: list[str], *, cwd: Path, output_file: Path) -> tuple[int, str]:
    """Run a preselected analyzer without shell execution or package writes."""
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, shell=False, check=False)
    raw = result.stdout + result.stderr
    output_file.write_text(raw, encoding="utf-8")
    return result.returncode, raw


def normalize_scanner_output(scanner: str, version: str, raw: str, *, source_root: Path) -> list[StaticFinding]:
    """Normalize known scanner output without interpreting arbitrary commands."""
    findings: list[StaticFinding] = []
    if scanner == "cppcheck":
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return findings
        for error in root.findall(".//error"):
            location = error.find("location")
            if location is None or not location.get("file"):
                continue
            path = Path(location.get("file", ""))
            try:
                relative = path.resolve().relative_to(source_root.resolve()).as_posix()
            except ValueError:
                continue
            findings.append(StaticFinding(scanner, version, error.get("id", "cppcheck"), relative, int(location.get("line", "0") or 0) or None, error.get("msg", "")))
    else:
        pattern = re.compile(r"^(.*?):(\d+):(\d+):\s+(warning|error):\s+(.*?)\s+\[([^]]+)\]", re.MULTILINE)
        for match in pattern.finditer(raw):
            path = Path(match.group(1))
            try:
                relative = path.resolve().relative_to(source_root.resolve()).as_posix()
            except ValueError:
                continue
            findings.append(StaticFinding(scanner, version, match.group(6), relative, int(match.group(2)), match.group(5)))
    return findings


def write_analysis_summary(output_dir: Path, inventory: dict, findings: list[StaticFinding]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "findings.json").write_text(json.dumps([item.as_dict() for item in findings], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
