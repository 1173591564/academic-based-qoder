"""
Visualization E2E Tests

Verifies the end-to-end pipeline:
  MCP tool → JSON structure → routeToComponent mapping → correct component type

Also tests the chat-done event JSON auto-detection logic
(matching the frontend's regex extraction from markdown responses).
"""

import json
import re
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# Mirror of frontend routeToComponent logic (ChatView.tsx L87-95)
# ============================================================

def route_to_component(parsed: dict) -> str:
    """Exact mirror of the TypeScript routeToComponent function.

    In JS, empty arrays [] are truthy, so we check 'is not None' to match.
    """
    if parsed.get("nodes") is not None and parsed.get("edges") is not None:
        return "citation_graph"
    if parsed.get("sections_toc") is not None or parsed.get("paper_id") is not None:
        return "paper_reader"
    if parsed.get("dimensions") is not None:
        return "quality_radar"
    if parsed.get("by_year") is not None or "parsed" in parsed:
        return "kb_dashboard"
    if parsed.get("our_metrics") is not None or parsed.get("comparison") is not None:
        return "experiment_metrics"
    if parsed.get("years") is not None and isinstance(parsed.get("years"), list):
        return "timeline"
    return "text"


# ============================================================
# Mirror of frontend JSON block extraction (ChatView.tsx L196)
# ============================================================

def extract_json_block(content: str) -> dict | None:
    """Extract the first ```json ... ``` block from markdown content."""
    match = re.search(r"```json\s*\n([\s\S]*?)\n```", content)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            return None
    return None


# ============================================================
# Tests: route_to_component logic
# ============================================================

class TestRouteToComponent:
    """Verify JSON structure → component type mapping matches frontend expectations."""

    def test_citation_graph_structure(self):
        """{nodes, edges} → citation_graph"""
        data = {"nodes": [{"id": "A", "title": "Paper A"}], "edges": [{"source": "A", "target": "B"}]}
        assert route_to_component(data) == "citation_graph"

    def test_citation_graph_empty_lists(self):
        """Empty nodes/edges still routes to citation_graph (error case from MCP)"""
        data = {"nodes": [], "edges": [], "error": "Neo4j not available"}
        assert route_to_component(data) == "citation_graph"

    def test_paper_card_with_toc(self):
        """{sections_toc: [...]} → paper_reader"""
        data = {"sections_toc": [{"title": "Introduction", "page": 1}], "title": "Test Paper"}
        assert route_to_component(data) == "paper_reader"

    def test_paper_card_with_paper_id(self):
        """{paper_id: "..."} → paper_reader"""
        data = {"paper_id": "01KT6MTARQMB6JVJNZA9PJVTS2", "title": "Test"}
        assert route_to_component(data) == "paper_reader"

    def test_quality_radar(self):
        """{dimensions: [...]} → quality_radar"""
        data = {"dimensions": [{"name": "novelty", "score": 8}, {"name": "clarity", "score": 7}]}
        assert route_to_component(data) == "quality_radar"

    def test_kb_dashboard_with_by_year(self):
        """{by_year: [...]} → kb_dashboard"""
        data = {"by_year": [{"year": 2023, "count": 45}], "total": 581}
        assert route_to_component(data) == "kb_dashboard"

    def test_kb_dashboard_with_parsed_key(self):
        """{parsed: 563, ...} → kb_dashboard (has 'parsed' key)"""
        data = {"parsed": 563, "notes": 120, "quality": 100}
        assert route_to_component(data) == "kb_dashboard"

    def test_experiment_metrics_with_comparison(self):
        """{comparison: [...]} → experiment_metrics"""
        data = {"comparison": [{"name": "accuracy", "ours": 0.85, "theirs": 0.87}]}
        assert route_to_component(data) == "experiment_metrics"

    def test_experiment_metrics_with_our_metrics(self):
        """{our_metrics: [...]} → experiment_metrics"""
        data = {"our_metrics": [{"name": "loss", "value": 0.23}], "runtime_seconds": 45.2}
        assert route_to_component(data) == "experiment_metrics"

    def test_timeline(self):
        """{years: [...]} → timeline"""
        data = {"years": [{"year": 2023, "papers": [...]}]}
        assert route_to_component(data) == "timeline"

    def test_text_fallback(self):
        """No matching structure → text"""
        data = {"some_random": "data"}
        assert route_to_component(data) == "text"

    def test_empty_dict(self):
        """Empty dict → text"""
        assert route_to_component({}) == "text"

    def test_nodes_without_edges_is_text(self):
        """{nodes: [...]} without edges → text (both required)"""
        data = {"nodes": [{"id": "A"}]}
        assert route_to_component(data) == "text"


# ============================================================
# Tests: JSON block extraction (chat-done event)
# ============================================================

class TestJsonBlockExtraction:
    """Verify JSON code block extraction from markdown chat responses."""

    def test_simple_json_block(self):
        """Extract a simple JSON block from markdown"""
        content = 'Here is the data:\n```json\n{"nodes": [], "edges": []}\n```\nDone.'
        result = extract_json_block(content)
        assert result is not None
        assert "nodes" in result
        assert "edges" in result

    def test_multiline_json_block(self):
        """Extract a multi-line JSON block"""
        content = '```json\n{\n  "nodes": [\n    {"id": "A", "title": "Paper A"}\n  ],\n  "edges": []\n}\n```'
        result = extract_json_block(content)
        assert result is not None
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["id"] == "A"

    def test_no_json_block(self):
        """No json block → None"""
        content = "This is just plain text without any JSON."
        assert extract_json_block(content) is None

    def test_invalid_json_block(self):
        """Malformed JSON → None"""
        content = '```json\n{not valid json}\n```'
        assert extract_json_block(content) is None

    def test_json_block_with_citation_graph_routes_correctly(self):
        """Full E2E: markdown → JSON extraction → route → citation_graph"""
        content = (
            'Based on my analysis:\n```json\n'
            '{"nodes": [{"id": "01K...", "title": "Attention"}], "edges": [{"source": "01K...", "target": "02K..."}]}'
            '\n```'
        )
        parsed = extract_json_block(content)
        assert parsed is not None
        assert route_to_component(parsed) == "citation_graph"

    def test_json_block_with_quality_radar_routes_correctly(self):
        """Full E2E: markdown → JSON extraction → route → quality_radar"""
        content = (
            'Quality assessment:\n```json\n'
            '{"dimensions": [{"name": "novelty", "score": 9}]}'
            '\n```'
        )
        parsed = extract_json_block(content)
        assert parsed is not None
        assert route_to_component(parsed) == "quality_radar"

    def test_json_block_first_match_only(self):
        """If multiple json blocks, extract the first one"""
        content = (
            '```json\n{"first": true}\n```\n'
            'more text\n'
            '```json\n{"second": true}\n```'
        )
        result = extract_json_block(content)
        assert result == {"first": True}


# ============================================================
# Tests: MCP tool return structure (requires no DB — tests error paths)
# ============================================================

class TestMcpReturnStructure:
    """Verify MCP tools return JSON with expected top-level keys even on error."""

    def test_citation_graph_error_has_nodes_edges(self):
        """When Neo4j unavailable, scholar_get_citation_graph still returns {nodes, edges}"""
        from scholar_mcp.server import scholar_get_citation_graph
        result = scholar_get_citation_graph()
        data = json.loads(result) if isinstance(result, str) else result
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_kb_dashboard_has_expected_keys(self):
        """scholar_get_kb_dashboard returns stats with expected structure"""
        from scholar_mcp.server import scholar_get_kb_dashboard
        result = scholar_get_kb_dashboard()
        data = json.loads(result) if isinstance(result, str) else result
        # Should have either by_year or parsed count or error
        assert any(k in data for k in ("by_year", "parsed", "error", "total"))

    def test_experiment_metrics_has_comparison(self):
        """scholar_get_experiment_metrics returns comparison or error"""
        from scholar_mcp.server import scholar_get_experiment_metrics
        result = scholar_get_experiment_metrics("nonexistent_paper_12345")
        data = json.loads(result) if isinstance(result, str) else result
        # Should return either comparison list or error
        assert any(k in data for k in ("comparison", "error", "our_metrics"))

    def test_timeline_has_years(self):
        """scholar_get_timeline returns years array"""
        from scholar_mcp.server import scholar_get_timeline
        result = scholar_get_timeline()
        data = json.loads(result) if isinstance(result, str) else result
        assert any(k in data for k in ("years", "error"))


# ============================================================
# Tests: Paper ID detection (MessageBubble.tsx)
# ============================================================

class TestPaperIdDetection:
    """Verify ULID and arXiv ID detection from text content."""

    def test_ulid_detection(self):
        """ULID pattern: 01K + 23 alphanumeric chars"""
        content = "I analyzed paper 01KT6MTARQMB6JVJNZA9PJVTS2 in depth."
        ulid_pattern = re.compile(r"01K[0-9A-Z]{23}")
        match = ulid_pattern.search(content)
        assert match is not None
        assert match.group() == "01KT6MTARQMB6JVJNZA9PJVTS2"

    def test_arxiv_id_detection(self):
        """arXiv ID pattern: 4 digits . 4-5 digits"""
        content = "The paper 2401.14019 introduces a new method."
        arxiv_pattern = re.compile(r"\b\d{4}\.\d{4,5}\b")
        match = arxiv_pattern.search(content)
        assert match is not None
        assert match.group() == "2401.14019"

    def test_multiple_ulids(self):
        """Multiple ULIDs in text are all detected"""
        content = "Compare 01KT6MTARQMB6JVJNZA9PJVTS2 with 01KT6MTASVH0M96VHM0CN44ASJ."
        ulid_pattern = re.compile(r"01K[0-9A-Z]{23}")
        matches = ulid_pattern.findall(content)
        assert len(matches) == 2

    def test_no_false_positive_year(self):
        """Year like 2023 should not match arXiv pattern"""
        content = "Published in 2023."
        arxiv_pattern = re.compile(r"\b\d{4}\.\d{4,5}\b")
        assert arxiv_pattern.search(content) is None
