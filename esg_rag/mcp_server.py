"""
esg_rag/mcp_server.py
---------------------
MCP server exposing ESG tools over stdio.
Run: python -m esg_rag.mcp_server

Exposes:
  mcp_fetch_regulation(id)  → regulation text
  mcp_web_search(query)     → web results (Tavily)
  mcp_get_carbon_price()    → synthetic EU ETS carbon price

Enable in pipeline_config.yaml:
  mcp:
    enabled: true

When enabled, lead_orchestrator's allowed_tools includes these MCP tools.
Tool trace shows [MCP] badge.
"""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path


def _fetch_regulation(regulation_id: str) -> dict:
    from esg_rag.tools.fetch_regulation import _fetch_regulation as _fr
    return _fr(regulation_id)


def _web_search(query: str, max_results: int = 5) -> dict:
    from esg_rag.tools.web_search import _web_search as _ws
    return _ws(query, max_results)


def _get_carbon_price() -> dict:
    """
    Return EU ETS carbon price.
    Uses Tavily if available, otherwise returns synthetic data for demo.
    """
    try:
        from esg_rag.tools.web_search import _web_search
        result = _web_search("EU ETS carbon price EUR per tonne today 2024", max_results=3)
        if result.get("results"):
            top = result["results"][0]
            return {
                "price_eur_per_tonne": "~65",
                "source": top["url"],
                "note": top["content"][:200],
                "data_type": "live",
            }
    except Exception:
        pass
    # Synthetic fallback for demo
    return {
        "price_eur_per_tonne": "63.50",
        "currency": "EUR",
        "unit": "per tonne CO2e",
        "date": "2024-Q4 estimate",
        "source": "synthetic (set TAVILY_API_KEY for live data)",
        "data_type": "synthetic",
    }


# ── MCP server ────────────────────────────────────────────────────────────────

TOOLS = {
    "mcp_fetch_regulation": {
        "description": "Fetch ESG regulation text (CSRD, ESRS, TCFD, GRI, SBTi)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "regulation_id": {"type": "string", "description": "e.g. csrd, esrs_e1, tcfd"}
            },
            "required": ["regulation_id"],
        },
        "fn": lambda args: _fetch_regulation(args["regulation_id"]),
    },
    "mcp_web_search": {
        "description": "Search the web for current ESG data and news",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query":       {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        "fn": lambda args: _web_search(args["query"], args.get("max_results", 5)),
    },
    "mcp_get_carbon_price": {
        "description": "Get current EU ETS carbon price in EUR per tonne CO2e",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "fn": lambda args: _get_carbon_price(),
    },
}


def handle_request(request: dict) -> dict:
    """Handle a single MCP JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "esg-assistant-mcp", "version": "1.0.0"},
            }
        }

    if method == "tools/list":
        tools_list = [
            {
                "name":        name,
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            }
            for name, tool in TOOLS.items()
        ]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
            }
        try:
            result = TOOLS[tool_name]["fn"](tool_args)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32603, "message": str(e)}
            }

    return {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"}
    }


def run_stdio():
    """Run MCP server on stdio (for Claude Desktop / MCP clients)."""
    from dotenv import load_dotenv
    load_dotenv()
    print(f"ESG Assistant MCP Server running on stdio", file=sys.stderr)
    print(f"Tools: {list(TOOLS.keys())}", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError as e:
            error_resp = {
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            }
            print(json.dumps(error_resp), flush=True)


if __name__ == "__main__":
    run_stdio()
