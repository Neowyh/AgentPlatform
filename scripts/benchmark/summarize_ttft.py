#!/usr/bin/env python3
"""Summarize benchmark samples without exposing request payloads."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "median_ms": None, "min_ms": None, "max_ms": None}
    return {
        "count": len(values),
        "median_ms": round(statistics.median(values), 1),
        "min_ms": round(min(values), 1),
        "max_ms": round(max(values), 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    by_count: dict[int, list[dict]] = {}
    for result in results:
        by_count.setdefault(int(result["count"]), []).append(result)
    output = []
    for count, samples in sorted(by_count.items()):
        valid = [
            sample
            for sample in samples
            if sample.get("run_to_first_token_ms") is not None
            and not sample.get("stream_error")
        ]
        output.append(
            {
                "count": count,
                "samples": len(samples),
                "failures": len(samples) - len(valid),
                "end_to_end_ttft": _summary(
                    [float(sample["end_to_end_ttft_ms"]) for sample in valid]
                ),
                "run_to_first_token": _summary(
                    [float(sample["run_to_first_token_ms"]) for sample in valid]
                ),
                "run_to_first_tool": _summary(
                    [
                        float(sample["run_to_first_tool_ms"])
                        for sample in valid
                        if sample.get("run_to_first_tool_ms") is not None
                    ]
                ),
            }
        )
    print(json.dumps({"source": str(args.input), "scenarios": output}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
