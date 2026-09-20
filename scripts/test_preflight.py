#!/usr/bin/env python3
"""Fail-fast checks for the prerequisites of a test lane.

The checker is deliberately read-only: it reports missing tools, lockfiles,
browser binaries, writable scratch space, and optional configuration without
installing packages or contacting application services.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from pnpm_command import resolve as resolve_pnpm

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
LOCAL_RUNTIME = ROOT / "local-runtime"

LANES = {
    "local-runtime": {"local_runtime": True},
    "backend-standard": {"backend": True, "socket": True},
    "backend-serial": {"backend": True, "socket": True},
    "backend-full": {"backend": True, "socket": True},
    "backend-llm": {"backend": True, "llm": True},
    "backend-external": {"backend": True, "socket": True},
    "backend-blocking-io": {"backend": True},
    # Rstest's browser-like harness binds a local worker port even for unit
    # tests, so catch socket-restricted environments before starting it.
    "frontend-standard": {"frontend": True, "socket": True},
    "frontend-core": {"frontend": True, "socket": True},
    "frontend-smoke": {"frontend": True, "browser": True, "socket": True},
    "frontend-mock-e2e": {"frontend": True, "browser": True, "socket": True},
    "frontend-visual": {"frontend": True, "browser": True, "socket": True},
    "frontend-a11y": {"frontend": True, "browser": True, "socket": True},
    "frontend-auth": {"frontend": True, "browser": True, "socket": True},
    "frontend-real": {"frontend": True, "browser": True, "socket": True},
    "frontend-stagehand": {
        "frontend": True,
        "browser": True,
        "socket": True,
        "llm": True,
    },
    "pr-standard": {"backend": True, "frontend": True, "browser": True, "socket": True},
    "core-full": {"backend": True, "frontend": True, "browser": True, "socket": True},
}


def _minimum_python(requirements: dict[str, bool]) -> tuple[int, int]:
    """Return the interpreter floor for a lane's supported runtime."""

    return (3, 8) if requirements.get("local_runtime") else (3, 12)


def check(label: str, ok: bool, detail: str = "") -> bool:
    state = "OK" if ok else "FAIL"
    print(f"[test-preflight] {state} {label}{(': ' + detail) if detail else ''}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lane", choices=sorted(LANES))
    args = parser.parse_args()
    req = LANES[args.lane]
    failed = False
    minimum_python = _minimum_python(req)
    failed |= not check(
        f"Python >= {minimum_python[0]}.{minimum_python[1]}",
        sys.version_info >= minimum_python,
        sys.version.split()[0],
    )

    if req.get("backend"):
        uv = shutil.which("uv")
        failed |= not check("uv", bool(uv), "install uv" if not uv else uv)
        failed |= not check("backend/uv.lock", (BACKEND / "uv.lock").is_file())
        # Resolve imports in uv's locked environment, rather than the agent's
        # ambient interpreter (which is often intentionally minimal).
        for module in ("pytest", "pytest_asyncio", "pytest_split"):
            available = _uv_import_ok(module)
            failed |= not check(
                module,
                available,
                "missing from uv dev group"
                if not available
                else "locked dev environment",
            )

    if req.get("local_runtime"):
        failed |= not check(
            "local-runtime/pyproject.toml", (LOCAL_RUNTIME / "pyproject.toml").is_file()
        )
        failed |= not check(
            "local-runtime pytest",
            _module_import_ok("pytest"),
            "install pytest"
            if not _module_import_ok("pytest")
            else "runtime environment",
        )
    if req.get("frontend"):
        failed |= not check("Node >= 22", _node_ok())
        try:
            pnpm = resolve_pnpm()
        except FileNotFoundError as exc:
            pnpm = []
            failed |= not check("pnpm/corepack", False, str(exc))
        failed |= not check(
            "pnpm/corepack",
            bool(pnpm),
            " ".join(pnpm) if pnpm else "install pnpm or enable Corepack",
        )
        if pnpm:
            pnpm_ok = _pnpm_version_ok(pnpm)
            failed |= not check(
                "pnpm invocation",
                pnpm_ok,
                "pnpm --version failed" if not pnpm_ok else "version command works",
            )
            expected = _expected_pnpm_version()
            actual = _pnpm_version(pnpm)
            version_match = not expected or not actual or actual == expected
            failed |= not check(
                "pnpm lockfile version",
                version_match,
                f"expected {expected}, found {actual}"
                if not version_match
                else (expected or "not pinned"),
            )
        failed |= not check(
            "frontend/pnpm-lock.yaml", (FRONTEND / "pnpm-lock.yaml").is_file()
        )
    if req.get("browser"):
        browser = FRONTEND / "node_modules" / "playwright"
        browser_ok = (
            browser.exists() or (FRONTEND / "node_modules" / "@playwright").exists()
        )
        failed |= not check(
            "Playwright package",
            browser_ok,
            "installed" if browser_ok else "run pnpm install",
        )
        raw_cache = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        cache = Path(raw_cache) if raw_cache else None
        browser_cache = (
            cache
            if cache and cache.exists()
            else Path.home() / ".cache" / "ms-playwright"
        )
        browser_ready = browser_cache.exists() and any(browser_cache.iterdir())
        failed |= not check(
            "Playwright browser cache",
            browser_ready,
            "install chromium before E2E" if not browser_ready else str(browser_cache),
        )
        if browser_ok and browser_ready:
            launched, detail = _playwright_launch()
            failed |= not check("Chromium launch", launched, detail)
    for directory in (ROOT / "logs", ROOT / ".deer-flow", Path(tempfile.gettempdir())):
        failed |= not check(f"writable {directory}", _mkdir_probe(directory))
    if req.get("socket"):
        if os.environ.get("TEST_PREFLIGHT_SKIP_SOCKET") == "1":
            print(
                "[test-preflight] WARN socket probe skipped by TEST_PREFLIGHT_SKIP_SOCKET=1"
            )
        else:
            try:
                with socket.socket() as sock:
                    sock.bind(("127.0.0.1", 0))
                check("local socket bind", True)
            except OSError as exc:
                failed |= not check("local socket bind", False, str(exc))
    if req.get("llm"):
        if os.environ.get("OPENAI_API_KEY"):
            print("[test-preflight] OK OPENAI_API_KEY is present (value hidden)")
        else:
            print(
                "[test-preflight] WARN OPENAI_API_KEY is absent; requires_llm tests will be skipped"
            )
    print(f"[test-preflight] lane={args.lane} status={'fail' if failed else 'ready'}")
    return 1 if failed else 0


def _node_ok() -> bool:
    node = shutil.which("node")
    if not node:
        return False
    try:
        import subprocess

        out = subprocess.check_output([node, "-p", "process.versions.node"], text=True)
        return int(out.split(".", 1)[0]) >= 22
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def _uv_import_ok(module: str) -> bool:
    uv = shutil.which("uv")
    if not uv:
        return False
    try:
        env = os.environ.copy()
        env.setdefault("UV_CACHE_DIR", "/tmp/deer-flow-uv-cache")
        result = subprocess.run(
            [uv, "run", "--locked", "python", "-c", f"import {module}"],
            cwd=BACKEND,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except OSError:
        return False


def _module_import_ok(module: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _pnpm_version_ok(command: list[str]) -> bool:
    try:
        env = os.environ.copy()
        env["XDG_DATA_HOME"] = env.get("TEST_PNPM_XDG", "/tmp/deer-flow-xdg")
        env["PNPM_HOME"] = env.get("TEST_PNPM_HOME", "/tmp/deer-flow-pnpm-home")
        result = subprocess.run(
            [*command, "--version"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except OSError:
        return False


def _pnpm_version(command: list[str]) -> str:
    try:
        env = os.environ.copy()
        env["XDG_DATA_HOME"] = env.get("TEST_PNPM_XDG", "/tmp/deer-flow-xdg")
        env["PNPM_HOME"] = env.get("TEST_PNPM_HOME", "/tmp/deer-flow-pnpm-home")
        value = subprocess.check_output(
            [*command, "--version"], env=env, text=True, stderr=subprocess.DEVNULL
        ).strip()
        return value if re.match(r"^\d+\.\d+\.\d+", value) else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _expected_pnpm_version() -> str:
    try:
        value = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8")).get(
            "packageManager", ""
        )
        return value.removeprefix("pnpm@")
    except (OSError, ValueError, AttributeError):
        return ""


def _mkdir_probe(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
        return True
    except OSError:
        return False


def _playwright_launch() -> tuple[bool, str]:
    """Exercise the project's Playwright install without starting a server."""
    script = "const {chromium}=require('@playwright/test'); (async()=>{const b=await chromium.launch({headless:true}); await b.close()})().catch(e=>{console.error(String(e).slice(0,300)); process.exit(1)})"
    try:
        result = subprocess.run(
            ["node", "-e", script],
            cwd=FRONTEND,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, type(exc).__name__
    return result.returncode == 0, (
        result.stderr.strip()[-300:] if result.returncode else "ready"
    )


if __name__ == "__main__":
    raise SystemExit(main())
