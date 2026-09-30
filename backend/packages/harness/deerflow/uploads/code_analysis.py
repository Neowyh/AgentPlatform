"""Deterministic, read-only static analysis for frozen Code Evidence packages."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

EvidenceMode = Literal["document", "code", "hybrid"]
FindingConfidence = Literal["confirmed", "high_risk_candidate", "pending_verification"]

_SOURCE_SUFFIXES = {".c", ".h", ".cc", ".cpp", ".cxx"}
_PYTHON_SUFFIXES = {".py"}
_LOG_SUFFIXES = {".log", ".txt", ".md"}

Language = Literal["c_cpp", "python"]
SCANNER_TIMEOUT_GRADE_THRESHOLD = 200
SMALL_PACKAGE_SCANNER_TIMEOUT_SECONDS = 120
LARGE_PACKAGE_SCANNER_TIMEOUT_SECONDS = 600


def scanner_timeout_seconds(source_file_count: int) -> int:
    """Tiered per-scanner budget: at most 200 source files get 120 seconds,
    larger packages get 600 seconds."""
    if source_file_count <= SCANNER_TIMEOUT_GRADE_THRESHOLD:
        return SMALL_PACKAGE_SCANNER_TIMEOUT_SECONDS
    return LARGE_PACKAGE_SCANNER_TIMEOUT_SECONDS


@dataclass(frozen=True)
class ScannerStatus:
    """One scanner's run account (the ``analysis/scanner_status.json`` contract).

    ``failed_to_start`` is an internal rollup input (a scanner that was found
    on PATH but could not be executed) and is deliberately not serialized: the
    on-disk contract carries the reason via ``skipped_reason``.
    """

    name: str
    available: bool
    version: str | None = None
    exit_code: int | None = None
    timed_out: bool = False
    skipped_reason: str | None = None
    failed_to_start: bool = False

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "available": self.available,
            "version": self.version,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "skipped_reason": self.skipped_reason,
        }


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


@dataclass(frozen=True)
class StaticAnalysisResult:
    """Everything one ``run_static_analysis`` pass produced for a package."""

    package_id: str
    inventory: dict
    findings: list[StaticFinding]
    statuses: list[ScannerStatus]

    @property
    def overall(self) -> Literal["completed", "scanners_unavailable", "partial"]:
        return overall_scanner_status(self.statuses)


def inventory_package(package_root: Path) -> dict:
    """Inventory only regular files below the validated package source root."""
    source_root = package_root / "source"
    files: list[str] = []
    source_files: list[str] = []
    python_files: list[str] = []
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
            if suffix in _PYTHON_SUFFIXES:
                python_files.append(relative)
            if suffix == ".h":
                headers.append(relative)
            if suffix in _LOG_SUFFIXES or path.name.lower() in {"fault.log", "error.log"}:
                logs.append(relative)
            if path.name in {"compile_commands.json", "CMakeLists.txt", "Makefile"}:
                build_metadata.append(relative)
    return {
        "files": files,
        "source_files": source_files,
        "python_files": python_files,
        "headers": headers,
        "logs": logs,
        "build_metadata": build_metadata,
        "compilation_configuration_verified": "compile_commands.json" in {Path(item).name for item in build_metadata},
    }


def detect_language(inventory: dict) -> Language | None:
    """Pick the package's scan language: C/C++ sources win; Python-only
    packages get the Python scanners; ``None`` means no supported sources."""
    if inventory.get("source_files"):
        return "c_cpp"
    if inventory.get("python_files"):
        return "python"
    return None


def confidence_for_finding(*, has_correlated_context: bool, is_static_alert: bool = True) -> FindingConfidence:
    """Apply the report contract: an alert alone is never confirmed."""
    if has_correlated_context and not is_static_alert:
        return "confirmed"
    if has_correlated_context:
        return "high_risk_candidate"
    return "high_risk_candidate" if is_static_alert else "pending_verification"


def fixed_scanner_commands(package_root: Path, output_dir: Path) -> list[tuple[str, list[str]]]:
    """Return fixed C/C++ scanner invocations whose binary is on PATH.

    Caller must execute without a shell. Unavailable scanners are dropped
    here; the orchestrating layer (``run_static_analysis``) is the one that
    must record them explicitly in scanner_status instead.
    """
    source = package_root / "source"
    output_dir.mkdir(parents=True, exist_ok=True)
    commands: list[tuple[str, list[str]]] = []
    if shutil.which("clang-tidy"):
        commands.append(("clang-tidy", _clang_tidy_command(package_root)))
    if shutil.which("cppcheck"):
        commands.append(("cppcheck", _cppcheck_command(source)))
    return commands


def _clang_tidy_command(package_root: Path) -> list[str]:
    source = package_root / "source"
    source_files = [str(path) for path in sorted(source.rglob("*")) if path.is_file() and path.suffix.lower() in _SOURCE_SUFFIXES]
    return ["clang-tidy", "--quiet", *source_files, "-p", str(source), "--", "-fsyntax-only"]


def _cppcheck_command(source: Path) -> list[str]:
    return ["cppcheck", "--enable=warning,style,performance,portability", "--xml", "--xml-version=2", str(source)]


def _ruff_command(source: Path) -> list[str]:
    return ["ruff", "check", "--output-format", "json", str(source)]


def _bandit_command(source: Path) -> list[str]:
    return ["bandit", "-f", "json", "-q", "-r", str(source)]


_SCANNER_VERSION_TIMEOUT_SECONDS = 15
_VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+")


def detect_scanner(name: str) -> tuple[bool, str | None]:
    """Locate a scanner binary on PATH and read its self-reported version.

    A binary that exists but cannot report a version still counts as
    available (``version=None``); the run outcome carries the details.
    """
    if shutil.which(name) is None:
        return False, None
    try:
        result = subprocess.run([name, "--version"], capture_output=True, text=True, shell=False, check=False, timeout=_SCANNER_VERSION_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return True, None
    match = _VERSION_PATTERN.search(f"{result.stdout}\n{result.stderr}")
    return True, match.group(0) if match else None


def overall_scanner_status(statuses: list[ScannerStatus]) -> Literal["completed", "scanners_unavailable", "partial"]:
    """Roll the per-scanner statuses up to the disclosure grade.

    - ``scanners_unavailable``: every scanner's binary is missing from the
      environment — the run must disclose that nothing could be scanned.
    - ``partial``: something ran but the environment or an execution failed
      (missing scanner among several, timeout, start failure).
    - ``completed``: every scanner that applied was available and finished
      (documented policy skips — e.g. clang-tidy without a compilation
      database — do not degrade the run).
    """
    if not statuses:
        return "completed"
    if all(not status.available for status in statuses):
        return "scanners_unavailable"
    failed = [status for status in statuses if status.available and (status.timed_out or status.failed_to_start)]
    if failed:
        return "partial"
    ran = [status for status in statuses if status.available and not status.skipped_reason and status.exit_code is not None]
    if not ran:
        return "partial"
    if any(not status.available for status in statuses):
        return "partial"
    return "completed"


def run_static_analysis(package_root: Path) -> StaticAnalysisResult:
    """Run the fixed read-only scanner set for one package's language.

    Dispatch: C/C++ sources get clang-tidy and cppcheck; Python-only sources
    get ruff and bandit, both strictly read-only. clang-tidy is skipped with a
    recorded reason when the package carries no compilation database. Every
    scanner ends up in the status list — unavailable binaries and skipped
    runs are disclosed, never dropped.
    """
    inventory = inventory_package(package_root)
    language = detect_language(inventory)
    if language is None:
        return StaticAnalysisResult(package_id=package_root.name, inventory=inventory, findings=[], statuses=[])
    source = package_root / "source"
    if language == "c_cpp":
        plan: list[tuple[str, Callable[[], list[str]]]] = [
            ("clang-tidy", lambda: _clang_tidy_command(package_root)),
            ("cppcheck", lambda: _cppcheck_command(source)),
        ]
        needs_compilation_database = {"clang-tidy"}
        file_count = len(inventory["source_files"])
    else:
        plan = [("ruff", lambda: _ruff_command(source)), ("bandit", lambda: _bandit_command(source))]
        needs_compilation_database = set()
        file_count = len(inventory["python_files"])
    timeout = scanner_timeout_seconds(file_count)
    statuses: list[ScannerStatus] = []
    findings: list[StaticFinding] = []
    for name, build_command in plan:
        available, version = detect_scanner(name)
        if not available:
            statuses.append(ScannerStatus(name, available=False, skipped_reason=f"{name} binary not found on PATH"))
            continue
        if name in needs_compilation_database and not inventory["compilation_configuration_verified"]:
            statuses.append(ScannerStatus(name, available=True, version=version, skipped_reason="missing compile_commands.json; clang-tidy requires a compilation database"))
            continue
        outcome = run_fixed_scanner(build_command(), cwd=package_root, output_dir=package_root / "analysis", timeout=timeout)
        statuses.append(
            ScannerStatus(
                name,
                available=True,
                version=version,
                exit_code=outcome.exit_code,
                timed_out=outcome.timed_out,
                failed_to_start=outcome.start_error is not None,
                skipped_reason=f"failed to start: {outcome.start_error}" if outcome.start_error else None,
            )
        )
        raw = outcome.stdout
        if name not in {"cppcheck", "ruff", "bandit"}:
            # clang-style text diagnostics may land on either stream; only the
            # XML producers must keep their results stream isolated.
            raw = f"{outcome.stdout}\n{outcome.stderr}"
        findings.extend(normalize_scanner_output(name, version or "unknown", raw, source_root=source))
    return StaticAnalysisResult(package_id=package_root.name, inventory=inventory, findings=findings, statuses=statuses)


@dataclass(frozen=True)
class ScannerRunResult:
    """Captured outcome of one scanner execution, stdout and stderr apart.

    cppcheck writes its results XML to stdout and progress to stderr, so the
    two streams must never be concatenated before parsing.
    """

    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    start_error: str | None = None


def _decode_stream(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_fixed_scanner(command: list[str], *, cwd: Path, output_dir: Path, timeout: int = SMALL_PACKAGE_SCANNER_TIMEOUT_SECONDS) -> ScannerRunResult:
    """Run a preselected analyzer without shell execution or package writes.

    Results (stdout) and progress/noise (stderr) are captured separately and
    archived under ``output_dir``. A scanner that cannot start — binary raced
    away, ``E2BIG`` argument overflow — is captured as ``start_error`` instead
    of raising, so one broken scanner never takes the analysis down.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, shell=False, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        outcome = ScannerRunResult(exit_code=124, stdout=_decode_stream(exc.stdout), stderr=_decode_stream(exc.stderr), timed_out=True)
    except OSError as exc:
        outcome = ScannerRunResult(exit_code=None, stdout="", stderr="", start_error=f"{type(exc).__name__}: {exc}")
    else:
        outcome = ScannerRunResult(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
    stem = Path(command[0]).name
    (output_dir / f"{stem}.stdout.txt").write_text(outcome.stdout, encoding="utf-8")
    stderr_note = outcome.stderr or outcome.start_error or (f"Scanner timed out after {timeout} seconds" if outcome.timed_out else "")
    (output_dir / f"{stem}.stderr.txt").write_text(stderr_note, encoding="utf-8")
    return outcome


def _relative_scanner_path(value: str, source_root: Path) -> str | None:
    path = Path(value)
    candidate = path if path.is_absolute() else source_root / path
    try:
        return candidate.resolve().relative_to(source_root.resolve()).as_posix()
    except ValueError:
        return None


def _json_findings(scanner: str, version: str, raw: str, source_root: Path, *, rule_key: str, message_key: str, line_key: str, filename_key: str = "filename", location_row: bool = False) -> list[StaticFinding]:
    """Shared JSON normalizer for ruff and bandit output shapes.

    Both scanners report findings as JSON documents; paths must resolve
    inside the package source root and every alert keeps the Finding
    Confidence contract: a static alert alone is never confirmed.
    """
    try:
        payload = json.loads(raw)
    except ValueError:
        return []
    entries = payload if isinstance(payload, list) else (payload.get("results") if isinstance(payload, dict) else None)
    if not isinstance(entries, list):
        return []
    findings: list[StaticFinding] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        if location_row:
            location = item.get("location") or {}
            row = location.get("row") if isinstance(location, dict) else None
            line = row if isinstance(row, int) else None
        else:
            line_value = item.get(line_key)
            line = line_value if isinstance(line_value, int) else None
        relative = _relative_scanner_path(str(item.get(filename_key, "")), source_root)
        if relative is None:
            continue
        rule = str(item.get(rule_key) or scanner)
        message = str(item.get(message_key) or "")
        findings.append(StaticFinding(scanner, version, rule, relative, line, message, confidence_for_finding(has_correlated_context=True)))
    return findings


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
            relative = _relative_scanner_path(location.get("file", ""), source_root)
            if relative is None:
                continue
            findings.append(StaticFinding(scanner, version, error.get("id", "cppcheck"), relative, int(location.get("line", "0") or 0) or None, error.get("msg", "")))
    elif scanner == "ruff":
        return _json_findings(scanner, version, raw, source_root, rule_key="code", message_key="message", line_key="location", location_row=True)
    elif scanner == "bandit":
        return _json_findings(scanner, version, raw, source_root, rule_key="test_id", message_key="issue_text", line_key="line_number")
    else:
        pattern = re.compile(r"^(.*?):(\d+):(\d+):\s+(warning|error):\s+(.*?)\s+\[([^]]+)\]", re.MULTILINE)
        for match in pattern.finditer(raw):
            relative = _relative_scanner_path(match.group(1), source_root)
            if relative is None:
                continue
            findings.append(StaticFinding(scanner, version, match.group(6), relative, int(match.group(2)), match.group(5)))
    return findings


def write_analysis_summary(output_dir: Path, result: StaticAnalysisResult) -> None:
    """Write the analysis artifacts: inventory, findings and scanner status.

    ``scanner_status.json`` is the disclosure contract consumed downstream:
    ``package_id``, one entry per scanner (name/available/version/exit_code/
    timed_out/skipped_reason) and the ``overall`` disclosure grade.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "inventory.json").write_text(json.dumps(result.inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "findings.json").write_text(json.dumps([item.as_dict() for item in result.findings], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    scanner_status = {
        "package_id": result.package_id,
        "scanners": [status.as_dict() for status in result.statuses],
        "overall": result.overall,
    }
    (output_dir / "scanner_status.json").write_text(json.dumps(scanner_status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
