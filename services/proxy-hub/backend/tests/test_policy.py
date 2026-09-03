"""Frozen Scholar catalog and deny-by-default policy tests."""

import ast
from pathlib import Path

import pytest

from proxy_hub.policy import (
    SCHOLAR_TOOL_CATALOG,
    InvalidToolPolicy,
    decide_tool,
    validate_tool_policy,
)


def registered_scholar_tools() -> set[str]:
    """Read decorated tool names without importing the Scholar runtime."""
    repository_root = Path(__file__).parents[4]
    server_path = repository_root / "scholar_mcp" / "server.py"
    tree = ast.parse(server_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "mcp"
                and decorator.func.attr == "tool"
            ):
                names.add(node.name)
    return names


def test_proxy_catalog_matches_registered_scholar_tools() -> None:
    assert set(SCHOLAR_TOOL_CATALOG) == registered_scholar_tools()
    assert len(SCHOLAR_TOOL_CATALOG) == 16


def test_policy_denies_unknown_unlisted_and_shared_writes() -> None:
    allowed = {"scholar_search", "scholar_auto_notes"}

    assert decide_tool("unknown", allowed).reason == "tool_unknown"
    assert decide_tool("scholar_info", allowed).reason == "tool_denied"
    assert decide_tool("scholar_auto_notes", allowed).reason == "workspace_write_denied"
    assert decide_tool("scholar_search", allowed).allowed is True
    assert (
        decide_tool(
            "scholar_auto_notes",
            allowed,
            allow_workspace_writes=True,
        ).allowed
        is True
    )


def test_policy_validation_rejects_unknown_names() -> None:
    with pytest.raises(InvalidToolPolicy, match="unknown_tool"):
        validate_tool_policy({"scholar_search", "unknown_tool"})
