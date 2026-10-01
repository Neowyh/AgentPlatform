#!/usr/bin/env python3
"""Select PR validation lanes from changed paths and explain each selection."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

CHANNEL_ORDER = (
    "governance",
    "backend-standard",
    "frontend-standard",
    "local-runtime",
    "frontend-smoke",
    "static-checks",
    "real-e2e",
)
BASE_CHANNELS = CHANNEL_ORDER[:-1]

DOC_NAMES = {"AGENTS.md", "CLAUDE.md"}
DOC_EXTENSIONS = {".md", ".mdx", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
INFRA_PATHS = (
    ".github/workflows/",
    "docker/",
    "deploy/",
)
INFRA_FILES = {
    "Makefile",
    "pyproject.toml",
    "uv.lock",
    "pnpm-lock.yaml",
    "package.json",
    "pnpm-workspace.yaml",
    "next.config.ts",
    "next.config.js",
    "next.config.mjs",
    "config.yaml",
    "config.example.yaml",
    "extensions_config.json",
    "extensions_config.example.json",
}
RISK_PARTS = (
    "auth",
    "rbac",
    "persistence",
    "migrations",
    "memory",
    "admin",
    "agents",
    "skills",
    "workflows",
    "runtime",
)


def _is_documentation_path(path: str) -> bool:
    if path.startswith("resources/skills/"):
        return False
    suffix = Path(path).suffix.lower()
    return path in DOC_NAMES or suffix in {".md", ".mdx"} or (path.startswith("docs/manual/screenshots/") and suffix in DOC_EXTENSIONS - {".md", ".mdx"})


def _is_docs_only(paths: list[str]) -> bool:
    return bool(paths) and all(_is_documentation_path(path) for path in paths)


def _is_high_risk(path: str) -> str | None:
    if path.startswith("resources/skills/"):
        return "public skills"
    if not path.startswith(("backend/", "frontend/")):
        return None
    parts = path.lower().split("/")
    for part in parts:
        if part == "auth" or part.startswith("auth_") or part == "auth.py":
            return "authentication"
        for risk in RISK_PARTS[1:]:
            singular = risk.rstrip("s")
            if part == risk or part.startswith(singular + "_") or part.startswith(singular + "."):
                return risk
    return None


def classify_changes(paths: list[str]) -> dict[str, object]:
    """Return a deterministic channel plan with a reason for every lane."""

    normalized = sorted({path.strip().replace("\\", "/").removeprefix("./") for path in paths if path.strip()})
    reasons: dict[str, list[str]] = {"governance": []}
    selected = {"governance"}

    def add(channel: str, reason: str) -> None:
        selected.add(channel)
        reasons.setdefault(channel, []).append(reason)

    if not normalized:
        reasons["governance"].append("no changed files; run governance checks")
    elif _is_docs_only(normalized):
        reasons["governance"].append("documentation-only change")
    else:
        reasons["governance"].append("all changes require ownership and guidance checks")
        unknown: list[str] = []
        high_risk: list[str] = []
        for path in normalized:
            parts = path.split("/")
            basename = parts[-1]
            risk = _is_high_risk(path)
            if risk:
                high_risk.append(f"{path}: {risk}")
            if path.startswith("backend/"):
                add("backend-standard", f"backend path: {path}")
                add("static-checks", f"backend code or test path: {path}")
            elif path.startswith("frontend/"):
                add("frontend-standard", f"frontend path: {path}")
                add("frontend-smoke", f"frontend behavior may affect browser flows: {path}")
                add("static-checks", f"frontend path: {path}")
            elif path.startswith("local-runtime/"):
                add("local-runtime", f"local-runtime path: {path}")
                add("static-checks", f"local-runtime path: {path}")
            elif path.startswith(INFRA_PATHS) or basename in INFRA_FILES:
                for channel in BASE_CHANNELS[1:]:
                    add(channel, f"build, configuration, or workflow input: {path}")
            elif path.startswith("scripts/") or path.startswith("tests/"):
                for channel in BASE_CHANNELS[1:]:
                    add(channel, f"shared test or tooling path: {path}")
            elif _is_documentation_path(path):
                continue
            else:
                unknown.append(path)

        if unknown:
            for channel in BASE_CHANNELS[1:]:
                for path in unknown:
                    add(channel, f"unclassified path expands validation: {path}")
        if high_risk:
            for risk in high_risk:
                add("real-e2e", f"high-risk path requires protected real E2E: {risk}")
        if selected == {"governance"}:
            reasons["governance"].append("documentation-only change")

    ordered = [channel for channel in CHANNEL_ORDER if channel in selected]
    normalized_reasons = {channel: sorted(set(reasons[channel])) for channel in ordered}
    return {
        "channels": ordered,
        "reasons": normalized_reasons,
        "changed_files": normalized,
        "docs_only": _is_docs_only(normalized),
    }


def _changed_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRD", f"{base}...{head}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="base commit or ref; use with --head")
    parser.add_argument("--head", help="head commit or ref; use with --base")
    parser.add_argument("--changed-files", nargs="*", help="explicit paths for tests")
    parser.add_argument("--github-output", help="append plan outputs to this GITHUB_OUTPUT file")
    args = parser.parse_args()
    if args.changed_files is not None:
        paths = args.changed_files
    elif args.base and args.head:
        try:
            paths = _changed_paths(args.base, args.head)
        except subprocess.CalledProcessError as exc:
            print(f"cannot compare {args.base}...{args.head}: {exc.stderr}", file=sys.stderr)
            return 2
    else:
        parser.error("provide --base and --head, or --changed-files")

    plan = classify_changes(paths)
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    print(json.dumps(plan, indent=2, sort_keys=True))
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as output:
            output.write(f"plan={encoded}\n")
            output.write(f"channels={','.join(plan['channels'])}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
