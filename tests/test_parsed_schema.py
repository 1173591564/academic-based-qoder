"""Parsed vNext schema, determinism, diagnostics, and compatibility tests."""

import copy
import json

import pymupdf
import pytest
from jsonschema import ValidationError

from scholar import db
from scholar.parsed_schema import (
    canonical_json_bytes,
    legacy_projection,
    validate_parsed_document,
)
from scholar.tex_parser import TeXParser


FIXTURE_ID = "PARSER_CONTRACT_FIXTURE"


@pytest.fixture
def fixture_dir(project_root):
    return project_root / "tests" / "fixtures" / "parser_contract" / "nested"


def test_fixture_matches_deterministic_golden_artifact(fixture_dir):
    parser = TeXParser()
    first = parser.parse_directory(fixture_dir, FIXTURE_ID)
    second = parser.parse_directory(fixture_dir, FIXTURE_ID)
    expected = json.loads(
        (fixture_dir.parent / "nested.expected.json").read_text(encoding="utf-8")
    )

    validate_parsed_document(first)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first == expected


def test_fixture_reports_loss_and_missing_input(fixture_dir):
    document = TeXParser().parse_directory(fixture_dir, FIXTURE_ID)

    assert document["diagnostics"]["warnings"] == [{
        "code": "missing_input",
        "stage": "include",
        "severity": "warning",
        "message": "TeX input could not be resolved: sections/missing",
        "locator": {
            "path": "main.tex",
            "target": "sections/missing",
        },
    }]
    assert document["diagnostics"]["losses"][0]["code"] == "clean_text_projection"
    assert document["diagnostics"]["losses"][0]["input_chars"] > (
        document["diagnostics"]["losses"][0]["output_chars"]
    )


def test_fixture_separates_mentions_entries_and_formula_collisions(fixture_dir):
    document = TeXParser().parse_directory(fixture_dir, FIXTURE_ID)

    assert document["citations"] == ["used2026"]
    assert {entry["ref_key"] for entry in document["bibliography"]} == {
        "used2026",
        "uncited2025",
    }
    used = next(
        entry
        for entry in document["bibliography"]
        if entry["ref_key"] == "used2026"
    )
    assert used["authors"] == ["Ada Lovelace", "Alan Mathison Turing"]
    assert len(document["formulas"]) == 2


def test_schema_rejects_incomplete_artifacts(fixture_dir):
    document = TeXParser().parse_directory(fixture_dir, FIXTURE_ID)
    incomplete = copy.deepcopy(document)
    del incomplete["source"]

    with pytest.raises(ValidationError):
        validate_parsed_document(incomplete)


def test_save_writes_vnext_and_legacy_projection(tmp_path, fixture_dir):
    parsed_dir = tmp_path / "parsed"
    document = TeXParser().parse_directory(fixture_dir, FIXTURE_ID)

    legacy_path = db.save_parsed(document, parsed_dir=parsed_dir)
    legacy = db.load_parsed(FIXTURE_ID, parsed_dir=parsed_dir)
    vnext = db.load_parsed_vnext(FIXTURE_ID, parsed_dir=parsed_dir)

    assert legacy_path == parsed_dir / f"{FIXTURE_ID}.json"
    assert legacy == legacy_projection(document)
    assert "schema_version" not in legacy
    assert vnext == document


def test_multiple_main_files_prefer_orchestrator(project_root):
    fixture = (
        project_root
        / "tests"
        / "fixtures"
        / "parser_contract"
        / "multiple_main"
    )
    document = TeXParser().parse_directory(fixture, "MULTIPLE_MAIN_FIXTURE")

    assert document["title"] == "Orchestrated Paper"
    assert document["main_tex_file"] == "main.tex"
    assert [section["heading"] for section in document["sections"]] == ["Selected"]


def test_malformed_tex_produces_structured_warnings(project_root):
    fixture = (
        project_root
        / "tests"
        / "fixtures"
        / "parser_contract"
        / "malformed"
    )
    document = TeXParser().parse_directory(fixture, "MALFORMED_FIXTURE")
    warning_codes = {
        warning["code"]
        for warning in document["diagnostics"]["warnings"]
    }

    assert warning_codes == {"unbalanced_braces", "unbalanced_environment"}


def test_synthetic_pdf_fixture_is_readable(project_root):
    path = (
        project_root
        / "tests"
        / "fixtures"
        / "parser_contract"
        / "synthetic.pdf"
    )

    with pymupdf.open(path) as document:
        assert document.page_count == 1
        assert "Synthetic MIT-licensed evidence." in document[0].get_text()
