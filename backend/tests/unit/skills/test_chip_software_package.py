from pathlib import Path

from ideer.skills.chip_software_package import (
    ChipSoftwareDocument,
    extract_chip_software_package,
    validate_source_set,
)


def document(
    name: str,
    kind: str,
    *,
    part: str = "DEER-M4",
    package: str = "LQFP64",
    content: str = "",
) -> ChipSoftwareDocument:
    return ChipSoftwareDocument(
        name=name,
        document_type=kind,
        part_number=part,
        package=package,
        source_location=f"{name} § 1 (p. 1)",
        text=content,
    )


def complete_documents(*extra: ChipSoftwareDocument) -> list[ChipSoftwareDocument]:
    return [
        document(
            "deer-m4-datasheet.pdf",
            "datasheet",
            content="""\
TOPIC: startup_reset | Reset vector is at 0x00000000 | source=deer-m4-datasheet.pdf § 4.1 (p. 12)
TOPIC: clock | HSE supports 8 MHz crystal | source=deer-m4-datasheet.pdf § 6.2 (p. 28)
PIN: PA0 | signal=UART1_TX | alternate_function=AF1 | peripheral=UART1 | interrupt=UART1_IRQn | source=deer-m4-datasheet.pdf § 7.3 (p. 41)
""",
        ),
        document(
            "deer-m4-reference-manual.pdf",
            "reference_manual",
            content="""\
TOPIC: memory | Flash starts at 0x08000000 | source=deer-m4-reference-manual.pdf § 2.1 (p. 19)
TOPIC: dma | DMA1 channel 1 serves UART1_TX | source=deer-m4-reference-manual.pdf § 9.4 (p. 188)
""",
        ),
        document(
            "deer-m4-errata.pdf",
            "errata",
            content="""\
TOPIC: errata_impact | UART1 may lose the first byte after wakeup | source=deer-m4-errata.pdf § 3.2 (p. 6)
""",
        ),
        *extra,
    ]


def test_user_callable_run_returns_two_auditable_artifacts() -> None:
    result = extract_chip_software_package(complete_documents(), target_part="DEER-M4", target_package="LQFP64")

    assert set(result.artifacts) == {"embedded-software-knowledge-brief.md", "chip-software-table.json"}
    assert "DEER-M4" in result.artifacts["embedded-software-knowledge-brief.md"]
    assert "LQFP64" in result.artifacts["embedded-software-knowledge-brief.md"]
    assert "startup_reset" in result.artifacts["embedded-software-knowledge-brief.md"]
    assert "deer-m4-datasheet.pdf § 4.1 (p. 12)" in result.artifacts["embedded-software-knowledge-brief.md"]
    assert any(row["pin"] == "PA0" for row in result.structured_rows)
    assert all(row["source"] for row in result.structured_rows)
    assert all(row["confidence"] in {"confirmed", "review_required"} for row in result.structured_rows)


def test_mixed_part_or_package_is_rejected_without_merging_facts() -> None:
    docs = complete_documents(document("other.pdf", "datasheet", part="DEER-M4", package="QFN48"))

    validation = validate_source_set(docs, target_part="DEER-M4", target_package="LQFP64")
    assert validation.accepted is False
    assert any("QFN48" in issue for issue in validation.issues)

    result = extract_chip_software_package(docs, target_part="DEER-M4", target_package="LQFP64")
    assert result.validation.accepted is False
    assert all(row["package"] == "LQFP64" for row in result.structured_rows)
    assert "QFN48" in "\n".join(result.validation.issues)


def test_missing_manual_and_errata_are_visible_as_gaps() -> None:
    result = extract_chip_software_package(
        [document("deer-m4-datasheet.pdf", "datasheet")],
        target_part="DEER-M4",
        target_package="LQFP64",
    )

    assert result.validation.accepted is True
    assert "reference_manual_or_programming_manual" in result.validation.gaps
    assert "errata" in result.validation.gaps
    assert "资料缺口" in result.artifacts["embedded-software-knowledge-brief.md"]


def test_conflicting_pin_evidence_is_review_required_in_both_artifacts() -> None:
    docs = complete_documents(
        document(
            "deer-m4-reference-manual.pdf",
            "reference_manual",
            content="PIN: PA0 | signal=SPI1_MOSI | alternate_function=AF5 | peripheral=SPI1 | interrupt=SPI1_IRQn | source=deer-m4-reference-manual.pdf § 10.1 (p. 210)",
        )
    )

    result = extract_chip_software_package(docs, target_part="DEER-M4", target_package="LQFP64")
    rows = [row for row in result.structured_rows if row["pin"] == "PA0"]
    assert rows
    assert all(row["confidence"] == "review_required" for row in rows)
    assert "需人工复核" in result.artifacts["embedded-software-knowledge-brief.md"]
    assert '"confidence": "review_required"' in result.artifacts["chip-software-table.json"]


def test_downstream_view_only_exposes_confirmed_rows() -> None:
    docs = complete_documents(
        document(
            "deer-m4-reference-manual.pdf",
            "reference_manual",
            content="PIN: PA0 | signal=SPI1_MOSI | alternate_function=AF5 | peripheral=SPI1 | interrupt=SPI1_IRQn | source=deer-m4-reference-manual.pdf § 10.1 (p. 210)",
        )
    )
    result = extract_chip_software_package(docs, target_part="DEER-M4", target_package="LQFP64")

    assert result.confirmed_rows
    assert all(row["confidence"] == "confirmed" for row in result.confirmed_rows)
    assert not any(row["signal"] == "SPI1_MOSI" for row in result.confirmed_rows)


def test_non_native_text_source_is_not_accepted() -> None:
    scanned = document("scan.pdf", "datasheet")
    scanned = ChipSoftwareDocument(**{**scanned.__dict__, "is_native_text": False})

    result = extract_chip_software_package([scanned], target_part="DEER-M4", target_package="LQFP64")

    assert result.validation.accepted is False
    assert any("native text" in issue for issue in result.validation.issues)


def test_skill_resource_is_present_and_offline_packaged() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    skill_file = repo_root / "resources/skills/chip-software-development-package/SKILL.md"
    assert skill_file.is_file()
    assert "read_document" in skill_file.read_text(encoding="utf-8")
    assert "review_required" in skill_file.read_text(encoding="utf-8")


def test_sanitized_acceptance_samples_cover_complete_gaps_mixing_conflict_and_cross_page() -> None:
    fixture_root = Path(__file__).resolve().parents[2] / "fixtures/chip_software_source_sets"

    def load_sample(name: str) -> list[ChipSoftwareDocument]:
        sample = fixture_root / name
        documents = []
        for path in sorted(sample.glob("*.txt")):
            kind = "errata" if path.name == "errata.txt" else "reference_manual" if "reference" in path.name else "datasheet"
            package = "QFN48" if "qfn48" in path.name else "LQFP64"
            documents.append(document(path.name, kind, package=package, content=path.read_text(encoding="utf-8")))
        return documents

    complete = extract_chip_software_package(load_sample("complete"), target_part="DEER-M4", target_package="LQFP64")
    assert len(complete.artifacts) == 2
    assert complete.confirmed_rows

    missing = extract_chip_software_package(load_sample("missing-reference"), target_part="DEER-M4", target_package="LQFP64")
    assert "reference_manual_or_programming_manual" in missing.validation.gaps

    mixed = extract_chip_software_package(load_sample("mixed-package"), target_part="DEER-M4", target_package="LQFP64")
    assert not mixed.validation.accepted
    assert all(row["package"] == "LQFP64" for row in mixed.structured_rows)

    conflict = extract_chip_software_package(load_sample("errata-conflict"), target_part="DEER-M4", target_package="LQFP64")
    assert any(row["confidence"] == "review_required" for row in conflict.structured_rows)

    cross_page = extract_chip_software_package(load_sample("cross-page-pin-table"), target_part="DEER-M4", target_package="LQFP64")
    assert all(row["confidence"] == "confirmed" for row in cross_page.structured_rows)
