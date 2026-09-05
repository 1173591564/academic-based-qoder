"""Typed records emitted by the LaTeXML projector."""

from dataclasses import dataclass, field


@dataclass
class SectionRecord:
    id: str
    parent_id: str | None
    xml_id: str | None
    node_kind: str
    semantic_role: str | None
    level: int
    ordinal: int
    title: str
    xml_pointer: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ContentRecord:
    id: str
    section_id: str | None
    parent_id: str | None
    xml_id: str | None
    node_kind: str
    semantic_role: str | None
    granularity: str
    ordinal: int
    title: str
    text: str
    tex: str | None
    xml_pointer: str
    metadata: dict = field(default_factory=dict)


@dataclass
class FormulaRecord:
    id: str
    content_node_id: str
    xml_id: str | None
    mode: str | None
    tex: str
    presentation_mathml: str | None
    content_mathml: str | None
    cmml_valid: bool | None
    xml_pointer: str
    metadata: dict = field(default_factory=dict)


@dataclass
class TableRecord:
    id: str
    content_node_id: str
    xml_id: str | None
    caption: str
    xml_pointer: str
    cells: list[dict]
    metadata: dict = field(default_factory=dict)


@dataclass
class ReferenceRecord:
    id: str
    xml_id: str | None
    citation_key: str | None
    raw_text: str
    title: str | None
    authors: list[str]
    year: int | None
    identifiers: dict
    xml_pointer: str


@dataclass
class CitationMentionRecord:
    id: str
    content_node_id: str | None
    reference_xml_id: str
    context_text: str
    xml_pointer: str


@dataclass
class ChunkRecord:
    id: str
    section_id: str | None
    source_node_ids: list[str]
    chunk_kind: str
    semantic_role: str | None
    ordinal: int
    content: str
    xml_pointer_start: str
    xml_pointer_end: str
    content_sha256: str


@dataclass
class PaperProjection:
    paper_id: str
    title: str
    normalized_title: str
    abstract: str
    authors: list[str]
    year: int | None
    venue: str
    sections: list[SectionRecord]
    content_nodes: list[ContentRecord]
    formulas: list[FormulaRecord]
    tables: list[TableRecord]
    references: list[ReferenceRecord]
    citation_mentions: list[CitationMentionRecord]
    chunks: list[ChunkRecord]
