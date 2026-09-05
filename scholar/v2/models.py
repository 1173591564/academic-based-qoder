"""Stable public models for the Scholar v2 query layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

ErrorCode = Literal[
    "INVALID_ARGUMENT",
    "NOT_FOUND",
    "AMBIGUOUS_ID",
    "SERVER_BUSY",
    "DEADLINE_EXCEEDED",
    "CANCELLED",
    "VECTOR_UNAVAILABLE",
    "GRAPH_UNAVAILABLE",
    "SNAPSHOT_UNAVAILABLE",
    "EXTERNAL_UNAVAILABLE",
    "INTERNAL",
]


class ScholarError(RuntimeError):
    """Typed error safe to expose through the MCP adapter."""

    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class EvidencePointer:
    paper_id: str
    node_id: str | None
    xml_artifact_id: str
    xml_pointer: str
    quote: str = ""
    fact_level: Literal["L0", "L1", "L2", "L3"] = "L1"
    extractor: str | None = None
    confidence: float = 1.0


@dataclass
class ToolEnvelope:
    """Bounded, snapshot-pinned response returned by v2 services."""

    request_id: str
    snapshot_id: str
    data: dict | list
    evidence: list[EvidencePointer] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    degraded: bool = False
    schema_version: str = "scholar.tool.v2"

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["evidence"] = [asdict(item) for item in self.evidence]
        return payload
