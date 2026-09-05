"""Exact Scholar tool authorization decisions."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

ToolEffect = Literal["read", "workspace_write"]

SCHOLAR_TOOL_CATALOG: Final[Mapping[str, ToolEffect]] = MappingProxyType(
    {
        "scholar_search": "read",
        "scholar_vec_search": "read",
        "scholar_info": "read",
        "scholar_section": "read",
        "scholar_passages": "read",
        "scholar_cite_network": "read",
        "scholar_graph_query": "read",
        "scholar_lineage": "read",
        "scholar_graph_stats": "read",
        "scholar_list_papers": "read",
        "scholar_arxiv_search": "read",
        "read_parsed_paper": "read",
        "scholar_read_output_file": "read",
        "read_skill": "read",
        "scholar_auto_notes": "workspace_write",
        "scholar_interests": "workspace_write",
    }
)


@dataclass(frozen=True)
class PolicyDecision:
    """One deny-by-default tool authorization result."""

    allowed: bool
    reason: str
    effect: ToolEffect | None


class InvalidToolPolicy(ValueError):
    """A policy contains names outside the frozen Scholar catalog."""


def validate_tool_policy(tool_names: object) -> tuple[str, ...]:
    """Return a stable policy after rejecting unknown tool names."""
    if not isinstance(tool_names, list | tuple | set | frozenset):
        raise InvalidToolPolicy("Scholar tool policy must be a collection")
    normalized: set[str] = set()
    for tool_name in tool_names:
        if not isinstance(tool_name, str):
            raise InvalidToolPolicy("Scholar tool names must be strings")
        normalized.add(tool_name)
    unknown = sorted(normalized - SCHOLAR_TOOL_CATALOG.keys())
    if unknown:
        raise InvalidToolPolicy(f"unknown Scholar tools: {', '.join(unknown)}")
    return tuple(sorted(normalized))


def decide_tool(
    tool_name: str,
    allowed_tools: Collection[str],
    *,
    allow_workspace_writes: bool = False,
) -> PolicyDecision:
    """Authorize one exact tool name without interpreting its arguments."""
    effect = SCHOLAR_TOOL_CATALOG.get(tool_name)
    if effect is None:
        return PolicyDecision(False, "tool_unknown", None)
    if tool_name not in allowed_tools:
        return PolicyDecision(False, "tool_denied", effect)
    if effect == "workspace_write" and not allow_workspace_writes:
        return PolicyDecision(False, "workspace_write_denied", effect)
    return PolicyDecision(True, "allowed", effect)


def decide_effective_tool(
    tool_name: str,
    capability_tools: Collection[str],
    tenant_tools: Collection[str],
    *,
    allow_workspace_writes: bool,
) -> PolicyDecision:
    """Apply capability, tenant, and backend restrictions to one exact tool."""
    effect = SCHOLAR_TOOL_CATALOG.get(tool_name)
    if effect is None:
        return PolicyDecision(False, "tool_unknown", None)
    if tool_name not in capability_tools:
        return PolicyDecision(False, "capability_tool_denied", effect)
    if tool_name not in tenant_tools:
        return PolicyDecision(False, "tenant_tool_denied", effect)
    if effect == "workspace_write" and not allow_workspace_writes:
        return PolicyDecision(False, "workspace_write_denied", effect)
    return PolicyDecision(True, "allowed", effect)


def backend_allows_workspace_writes(capacity: Mapping[str, object]) -> bool:
    """Allow writes only when backend metadata declares tenant isolation."""
    return capacity.get("workspace_isolation") == "tenant"
