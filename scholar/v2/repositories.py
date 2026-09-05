"""Stable repository facade composed from focused query modules."""

from .evidence_repository import EvidenceRepository
from .graph_repository import GraphRepository
from .paper_repository import PaperRepository
from .passage_repository import PassageRepository


class ScholarRepository(
    PassageRepository, GraphRepository, EvidenceRepository, PaperRepository
):
    pass


__all__ = ["ScholarRepository"]
