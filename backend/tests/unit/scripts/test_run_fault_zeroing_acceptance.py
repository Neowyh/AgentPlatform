from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_fault_zeroing_acceptance.py"


def load_acceptance_script():
    spec = importlib.util.spec_from_file_location("run_fault_zeroing_acceptance", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_case_argument_selects_only_requested_case(monkeypatch) -> None:
    acceptance = load_acceptance_script()
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), "--user-id", "user-1", "--case", "case_01_wind_tunnel_heat_flux_drift"])

    args = acceptance._parse_args()

    assert args.case == "case_01_wind_tunnel_heat_flux_drift"
    assert [path.name for path in acceptance._case_dirs(args.case)] == ["case_01_wind_tunnel_heat_flux_drift"]


def test_case_argument_defaults_to_all_cases() -> None:
    acceptance = load_acceptance_script()

    case_names = [path.name for path in acceptance._case_dirs(None)]

    assert len(case_names) >= 3
    assert "case_02" in case_names[1]
    assert "case_03" in case_names[2]
