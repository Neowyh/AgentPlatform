#!/usr/bin/env python3
"""Validate fault-zeroing agent output artifacts.

Thin CLI shim over the versioned Result Contract
(``ideer.fault_zeroing.contract``).  The contract module is the single
source of truth for the semantic rules; this shim keeps the offline CLI
working without a backend virtualenv by falling back to a direct file
import of the contract module inside the repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_FALLBACK_CONTRACT_PATH = (
    _SCRIPT_DIR.parent
    / "backend"
    / "packages"
    / "harness"
    / "ideer"
    / "fault_zeroing"
    / "contract.py"
)


def _load_contract_module() -> Any:
    try:
        from ideer.fault_zeroing import contract as module
    except ImportError:
        module = None
    if module is not None:
        return module
    if _FALLBACK_CONTRACT_PATH.is_file():
        spec = importlib.util.spec_from_file_location(
            "fault_zeroing_contract", _FALLBACK_CONTRACT_PATH
        )
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    print(
        "fault-zeroing result contract module is unavailable "
        f"(expected {_FALLBACK_CONTRACT_PATH})",
        file=sys.stderr,
    )
    raise SystemExit(2)


_contract = _load_contract_module()

# Re-exported contract surface (legacy imports keep working).
REQUIRED_OUTPUTS = _contract.REQUIRED_OUTPUTS
REQUIRED_COVERAGE = _contract.REQUIRED_COVERAGE
REQUIRED_REPORT_SECTIONS = _contract.REQUIRED_REPORT_SECTIONS
REQUIRED_STAGE_MARKERS = _contract.REQUIRED_STAGE_MARKERS
STATUS_VALUES = _contract.STATUS_VALUES
VERIFICATION_STATUS_VALUES = _contract.VERIFICATION_STATUS_VALUES
CONFIDENCE_VALUES = _contract.CONFIDENCE_VALUES
EVIDENCE_GRADES = _contract.EVIDENCE_GRADES
CONTRACT_VERSION = _contract.CONTRACT_VERSION
SUPPORTED_CONTRACT_VERSIONS = _contract.SUPPORTED_CONTRACT_VERSIONS
ContractFinding = _contract.ContractFinding
ContractVerdict = _contract.ContractVerdict
evaluate_result_contract = _contract.evaluate_result_contract

# Legacy alias: ValidationResult is now the structured ContractVerdict, which
# keeps ``.ok`` and ``.errors`` with identical message texts.
ValidationResult = _contract.ContractVerdict


def validate_outputs(
    outputs_dir: str | Path, schema_path: str | Path | None = None
) -> Any:
    return _contract.evaluate_result_contract(
        outputs_dir,
        schema_path=schema_path,
        repo_root=_SCRIPT_DIR.parent,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate fault-zeroing agent output files."
    )
    parser.add_argument(
        "--outputs-dir",
        required=True,
        help="Directory containing the five fault-zeroing outputs.",
    )
    parser.add_argument(
        "--schema",
        default=str(_contract.default_schema_path(_SCRIPT_DIR.parent)),
        help="Path to fault_tree.schema.json.",
    )
    parser.add_argument(
        "--contract-version",
        default=None,
        help="Pin the Result Contract semantic version for this evaluation.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the structured contract verdict as JSON.",
    )
    args = parser.parse_args(argv)

    verdict = _contract.evaluate_result_contract(
        args.outputs_dir,
        contract_version=args.contract_version,
        schema_path=args.schema,
        repo_root=_SCRIPT_DIR.parent,
    )
    if args.json:
        print(verdict.to_json())
        return 0 if verdict.ok else 1

    if verdict.ok:
        print("fault-zeroing outputs validation passed")
        return 0

    print("fault-zeroing outputs validation failed", file=sys.stderr)
    for error in verdict.errors:
        print(f"- {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
