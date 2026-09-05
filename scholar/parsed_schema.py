"""Versioned parsed-paper artifacts and legacy search projections."""

import hashlib
import json
from pathlib import Path
from typing import Optional

from jsonschema import Draft202012Validator


PARSED_SCHEMA_VERSION = "3.0.0"
PARSER_NAME = "scholar-tex"
PARSER_VERSION = "3.0.0"
SCHEMA_PATH = Path(__file__).parent / "schemas" / "parsed-vnext.schema.json"
VNEXT_DIRNAME = "vnext"
_VNEXT_FIELDS = {
    "schema_version",
    "parser",
    "source",
    "metadata_assertions",
    "diagnostics",
}


def canonical_json_bytes(value: object) -> bytes:
    """Serialize an artifact deterministically for hashes and golden tests."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def stable_id(namespace: str, value: object) -> str:
    """Return a stable SHA-256 identifier for parser-owned records."""
    digest = hashlib.sha256(
        namespace.encode("utf-8") + b"\0" + canonical_json_bytes(value)
    ).hexdigest()
    return f"sha256:{digest}"


def parser_config_hash() -> str:
    """Identify the parser configuration that produced an artifact."""
    return stable_id(
        "parser-config",
        {
            "clean_text_projection": 1,
            "include_resolution": 1,
            "metadata_assertions": 1,
        },
    )


def legacy_projection(document: dict) -> dict:
    """Project parsed vNext data to the fields consumed by current readers."""
    return {
        key: value
        for key, value in document.items()
        if key not in _VNEXT_FIELDS
    }


def metadata_assertions(legacy: dict, main_file: str) -> list[dict]:
    """Build source-qualified metadata assertions from TeX extraction."""
    assertions = []
    confidence = {
        "title": 0.85,
        "authors": 0.65,
        "year": 0.35,
        "venue": 0.4,
        "arxiv_id": 0.8,
        "abstract": 0.8,
    }
    for field in ("title", "authors", "year", "venue", "arxiv_id", "abstract"):
        value = legacy.get(field)
        if value in (None, "", []):
            continue
        assertion = {
            "field": field,
            "value": value,
            "source_kind": "tex",
            "source_locator": {"path": main_file},
            "confidence": confidence[field],
            "selected": True,
        }
        assertion["id"] = stable_id(
            "metadata-assertion",
            {
                "paper_id": legacy["paper_id"],
                **assertion,
            },
        )
        assertions.append(assertion)
    return assertions


def _deduplicate(records: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for record in records:
        key = canonical_json_bytes(record)
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def build_parsed_document(
    legacy: dict,
    *,
    source: dict,
    warnings: Optional[list[dict]] = None,
    losses: Optional[list[dict]] = None,
) -> dict:
    """Add parser lineage, source facts, assertions, and diagnostics."""
    document = {
        **legacy,
        "schema_version": PARSED_SCHEMA_VERSION,
        "parser": {
            "name": PARSER_NAME,
            "version": PARSER_VERSION,
            "config_hash": parser_config_hash(),
        },
        "source": source,
        "metadata_assertions": metadata_assertions(
            legacy,
            source["main_file"],
        ),
        "diagnostics": {
            "warnings": _deduplicate(warnings or []),
            "losses": _deduplicate(losses or []),
        },
    }
    validate_parsed_document(document)
    return document


def validate_parsed_document(document: dict) -> None:
    """Validate a parsed vNext artifact against the committed JSON Schema."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(document)
