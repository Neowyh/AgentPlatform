#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

LENGTH_LIMITS = {"short": 300, "medium": 600, "long": 1500}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--length", default="medium", choices=list(LENGTH_LIMITS.keys()))
    args = ap.parse_args()

    text = Path(args.target).read_text(encoding="utf-8", errors="ignore")
    max_len = LENGTH_LIMITS[args.length]

    ok = True
    reasons = []

    has_summary = re.search(r"^##\s*摘要", text, re.MULTILINE)
    has_points = re.search(r"^###\s*核心要点", text, re.MULTILINE)
    has_keywords = re.search(r"^###\s*关键词", text, re.MULTILINE)

    if not has_summary:
        ok = False
        reasons.append("missing summary heading")
    if not has_points:
        ok = False
        reasons.append("missing key points heading")
    if not has_keywords:
        ok = False
        reasons.append("missing keywords heading")

    summary_block = ""
    if has_summary:
        m = re.search(r"^##\s*摘要\n([\s\S]+?)(?=\n### |\Z)", text, re.MULTILINE)
        summary_block = m.group(1).strip() if m else ""

    if len(summary_block) > max_len:
        ok = False
        reasons.append("summary block exceeds length limit")

    points = [ln for ln in text.splitlines() if ln.strip().startswith("- ")]
    if has_points:
        point_count = len(points)
        if point_count < 3 or point_count > 6:
            ok = False
            reasons.append("points count out of range")

    urls = re.findall(r"https?://[^)\s]+", text)
    if urls:
        ok = False
        reasons.append("external urls found")

    print("pass:true" if ok else "pass:false")
    print("reasons:", "; ".join(reasons) if reasons else "ok")


if __name__ == "__main__":
    main()
