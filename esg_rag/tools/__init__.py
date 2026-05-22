"""
esg_rag/tools/__init__.py
-------------------------
Central tool registry. Every tool module calls register() at import time.

TOOLS dict: {name: {"schema": dict, "fn": callable, "description": str}}

The agent (Phase 6) reads TOOLS to build its tool list for Albert.
Each tool follows the OpenAI function-calling schema.

Usage:
    from esg_rag.tools import TOOLS, call_tool
    result = call_tool("retrieve", {"query": "Apple Scope 1 emissions"})
"""

from __future__ import annotations

from typing import Any, Callable

TOOLS: dict[str, dict[str, Any]] = {}


def register(
    name: str,
    description: str,
    parameters: dict[str, Any],
    fn: Callable,
) -> None:
    """Register a tool. Called at module import time by each tool file."""
    TOOLS[name] = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "fn": fn,
    }


def call_tool(name: str, args: dict[str, Any]) -> Any:
    """Execute a registered tool by name with the given arguments."""
    if name not in TOOLS:
        raise ValueError(f"Unknown tool: {name}. Available: {list(TOOLS.keys())}")
    return TOOLS[name]["fn"](**args)


def to_openai_schema() -> list[dict[str, Any]]:
    """
    Return tools in OpenAI function-calling format for Albert's chat endpoint.
    Pass this to albert.chat(messages, tools=to_openai_schema()).
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in TOOLS.values()
    ]


def load_all(config: dict | None = None) -> None:
    """
    Import all enabled tool modules so they self-register.
    Call this once at agent startup.
    """
    cfg = (config or {}).get("agent", {}).get("tools", {})

    if cfg.get("retrieve", True):
        import esg_rag.tools.retrieve_tool        # noqa: F401
    if cfg.get("list_documents", True):
        import esg_rag.tools.list_documents       # noqa: F401
    if cfg.get("read_table", True):
        import esg_rag.tools.read_table           # noqa: F401
    if cfg.get("compute", True):
        import esg_rag.tools.compute              # noqa: F401
    if cfg.get("compare_documents", False):
        import esg_rag.tools.compare_documents    # noqa: F401
    if cfg.get("extract_kpis", False):
        import esg_rag.tools.extract_kpis         # noqa: F401
    if cfg.get("fetch_regulation", False):
        import esg_rag.tools.fetch_regulation     # noqa: F401
    if cfg.get("web_search", False):
        import esg_rag.tools.web_search           # noqa: F401
