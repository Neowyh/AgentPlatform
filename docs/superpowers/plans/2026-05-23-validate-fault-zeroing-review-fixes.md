# Fault-Zeroing Validator Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two validator false negatives reported in review: expected-analysis evidence sources with line suffixes, and missing coverage-matrix rows hidden by mentions elsewhere in the report.

**Architecture:** Keep the validator as a single script and make the smallest rule changes in `scripts/validate_fault_zeroing_outputs.py`. Add regression tests in `backend/tests/test_validate_fault_zeroing_outputs.py` that fail on the current implementation before changing production code.

**Tech Stack:** Python 3.12, pytest, ruff-formatted script style, GitNexus impact/detect-change workflow.

---

## Current Findings

- `EXPECTED_ANALYSIS_PATTERN` at `scripts/validate_fault_zeroing_outputs.py:47` only accepts end of string, `#`, or `?` immediately after `.md`, so `06_expected_analysis.md:L3` and `06_expected_analysis.md 第3行` are not rejected.
- `_validate_report()` at `scripts/validate_fault_zeroing_outputs.py:444-446` checks `REQUIRED_COVERAGE` against all `report_text`, so a missing `资料覆盖矩阵` row can be masked by the same category appearing in `遗留风险` or another section.
- Existing tests cover `#L3/#L10` evidence suffixes and a simple matrix-row deletion, but they do not encode the two false-negative shapes from the review.
- GitNexus impact check before this plan returned LOW risk for both `_is_expected_analysis_source` and `_validate_report`; direct upstream callers are limited to the validator flow.

## Files

- Modify: `scripts/validate_fault_zeroing_outputs.py`
  - Broaden expected-analysis source matching.
  - Add a helper that extracts only the `资料覆盖矩阵` table rows.
  - Scope required coverage checks and missing-material row checks to those rows.
- Modify: `backend/tests/test_validate_fault_zeroing_outputs.py`
  - Add parameterized suffix regression coverage for expected-analysis evidence sources.
  - Harden matrix coverage regression so the missing category appears outside the matrix.

## Task 1: Add Expected-Analysis Source Suffix Regressions

**Files:**
- Modify: `backend/tests/test_validate_fault_zeroing_outputs.py`

- [ ] **Step 1: Add a failing parameterized test**

Insert this test after `test_expected_analysis_file_cannot_be_root_cause_evidence`:

```python
@pytest.mark.parametrize(
    "source",
    [
        "06_expected_analysis.md:L3",
        "06_expected_analysis.md 第3行",
        "06_expected_analysis.md第3行",
        "cases/case_01_expected_analysis.md：第10行",
    ],
)
def test_expected_analysis_file_cannot_use_line_suffixes(tmp_path: Path, source: str) -> None:
    fault_tree = valid_fault_tree()
    fault_tree["evidence"][0]["source"] = source

    assert_invalid(write_outputs(tmp_path, fault_tree), "expected-analysis files cannot be used as evidence")
```

- [ ] **Step 2: Verify the new test fails before implementation**

Run:

```bash
cd backend && pytest tests/test_validate_fault_zeroing_outputs.py::test_expected_analysis_file_cannot_use_line_suffixes -q
```

Expected: FAIL for at least the `:L3` and ` 第3行` cases because the current regex does not match those suffixes.

## Task 2: Broaden Expected-Analysis Source Matching

**Files:**
- Modify: `scripts/validate_fault_zeroing_outputs.py`
- Test: `backend/tests/test_validate_fault_zeroing_outputs.py`

- [ ] **Step 1: Update the regex**

Replace the existing `EXPECTED_ANALYSIS_PATTERN` definition with:

```python
EXPECTED_ANALYSIS_PATTERN = re.compile(
    r"(?:^|[/\\])[^/\\]*_expected_analysis\.md(?=$|[^\w./\\-]|第)",
    re.IGNORECASE,
)
```

This keeps the original path-segment requirement, avoids matching extensions such as `.mdx` or `.md.bak`, and accepts common citation suffix separators after `.md`: anchors, query/line markers, ASCII and full-width colons, whitespace, Chinese `第N行`, and punctuation used in prose citations.

- [ ] **Step 2: Run the focused suffix test**

Run:

```bash
cd backend && pytest tests/test_validate_fault_zeroing_outputs.py::test_expected_analysis_file_cannot_use_line_suffixes -q
```

Expected: PASS.

- [ ] **Step 3: Run the existing expected-analysis tests**

Run:

```bash
cd backend && pytest tests/test_validate_fault_zeroing_outputs.py::test_expected_analysis_file_cannot_be_root_cause_evidence tests/test_validate_fault_zeroing_outputs.py::test_expected_analysis_file_cannot_be_bottom_event_evidence -q
```

Expected: PASS, proving existing `#L3/#L10` behavior is preserved.

## Task 3: Add Coverage-Matrix Scope Regression

**Files:**
- Modify: `backend/tests/test_validate_fault_zeroing_outputs.py`

- [ ] **Step 1: Harden the existing coverage-matrix test**

Replace `test_material_coverage_matrix_must_cover_required_categories` with:

```python
def test_material_coverage_matrix_must_cover_required_categories(tmp_path: Path) -> None:
    report = valid_report().replace("| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |\n", "")
    report = report.replace(
        "暂无缺失资料风险；BE-02 仍待验证。",
        "历史或复核记录只在遗留风险中提及，BE-02 仍待验证。",
    )

    assert_invalid(write_outputs(tmp_path, report=report), "资料覆盖矩阵缺少：历史或复核记录")
```

This test encodes the exact review failure mode: the category exists in the report text, but not in the matrix row set.

- [ ] **Step 2: Verify the hardened test fails before implementation**

Run:

```bash
cd backend && pytest tests/test_validate_fault_zeroing_outputs.py::test_material_coverage_matrix_must_cover_required_categories -q
```

Expected: FAIL on the current validator because `历史或复核记录` appears in `遗留风险`, masking the missing matrix row.

## Task 4: Scope Coverage Checks to Matrix Rows

**Files:**
- Modify: `scripts/validate_fault_zeroing_outputs.py`
- Test: `backend/tests/test_validate_fault_zeroing_outputs.py`

- [ ] **Step 1: Add a focused helper near `_section_text`**

Insert this helper above `_section_text`:

```python
def _coverage_matrix_rows(report_text: str) -> list[str]:
    matrix_section = _section_text(report_text, "资料覆盖矩阵")
    rows: list[str] = []
    for line in matrix_section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.match(r"^\|\s*:?-{3,}:?\s*(?:\||$)", stripped):
            continue
        if "类别" in stripped and "检查结果" in stripped:
            continue
        rows.append(stripped)
    return rows
```

The helper deliberately reads only the markdown section headed `资料覆盖矩阵`, ignores header/separator rows, and returns data rows.

- [ ] **Step 2: Replace the broad report-text coverage check**

In `_validate_report()`, replace:

```python
missing_coverage = [category for category in REQUIRED_COVERAGE if category not in report_text]
if missing_coverage:
    result.add(f"资料覆盖矩阵缺少：{'、'.join(missing_coverage)}")
```

with:

```python
coverage_rows = _coverage_matrix_rows(report_text)
missing_coverage = [
    category
    for category in REQUIRED_COVERAGE
    if not any(category in row for row in coverage_rows)
]
if missing_coverage:
    result.add(f"资料覆盖矩阵缺少：{'、'.join(missing_coverage)}")
```

- [ ] **Step 3: Reuse the scoped rows for missing-material risk checks**

In `_validate_report()`, replace:

```python
coverage_rows = [
    line
    for line in report_text.splitlines()
    if line.strip().startswith("|") and any(category in line for category in REQUIRED_COVERAGE)
]
missing_rows = [line for line in coverage_rows if "缺失" in line or "未提供" in line or "未覆盖" in line]
```

with:

```python
missing_rows = [line for line in coverage_rows if "缺失" in line or "未提供" in line or "未覆盖" in line]
```

This avoids a second whole-report table scan and keeps both matrix-related checks on the same row set.

- [ ] **Step 4: Run the focused matrix test**

Run:

```bash
cd backend && pytest tests/test_validate_fault_zeroing_outputs.py::test_material_coverage_matrix_must_cover_required_categories -q
```

Expected: PASS.

## Task 5: Full Validator Regression

**Files:**
- Test: `backend/tests/test_validate_fault_zeroing_outputs.py`
- Inspect: `scripts/validate_fault_zeroing_outputs.py`

- [ ] **Step 1: Run the full validator test module**

Run:

```bash
cd backend && pytest tests/test_validate_fault_zeroing_outputs.py -q
```

Expected: PASS for the whole module.

- [ ] **Step 2: Run syntax/format-adjacent checks for the touched script**

Run:

```bash
python3 -m py_compile scripts/validate_fault_zeroing_outputs.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run GitNexus change detection before commit**

Run GitNexus change detection:

```text
gitnexus_detect_changes(scope="all", repo="ideer")
```

Expected: changed symbols limited to `EXPECTED_ANALYSIS_PATTERN`, `_validate_report`, the new `_coverage_matrix_rows` helper, and the validator tests. If unrelated symbols appear, inspect the diff before committing.

- [ ] **Step 4: Inspect git diff**

Run:

```bash
git diff -- scripts/validate_fault_zeroing_outputs.py backend/tests/test_validate_fault_zeroing_outputs.py
```

Expected: only the regex, matrix-row extraction, and regression tests changed.

## Anti-Regression Rules

- Every future validator bugfix should start with a failing `backend/tests/test_validate_fault_zeroing_outputs.py` regression that reproduces the exact false negative.
- Coverage-matrix assertions must never search the full report text when the requirement is about rows in `资料覆盖矩阵`.
- Source-file bans should treat line references as citation metadata, not as part of the file identity.
- Before committing validator changes, run the focused test, the full validator test module, and GitNexus `detect_changes`.

## Self-Review

- Spec coverage: Task 1 and Task 2 cover expected-analysis sources with line suffixes. Task 3 and Task 4 cover complete coverage-matrix rows. Task 5 covers validation and change-scope checks.
- Placeholder scan: no unresolved placeholder steps remain.
- Type consistency: helper signatures use existing `str -> list[str]` style; tests follow the existing `assert_invalid(write_outputs(...), expected)` pattern.
