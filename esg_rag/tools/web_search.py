"""
esg_rag/tools/web_search.py
----------------------------
Tool: web_search
Schema: {query, max_results?}

Wraps Tavily SDK for live web search.
Used when:
  - out_of_corpus questions (current carbon prices, latest news)
  - self_correct flags needs_web_search=True

Requires TAVILY_API_KEY in .env
"""

from __future__ import annotations

import os

from esg_rag.tools import register


def _web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web for current information not in the ESG report index.
    Use for: current carbon prices, latest regulatory updates, live company news.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return {
            "error": "TAVILY_API_KEY not set in .env — web search unavailable",
            "query": query,
            "results": [],
        }

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
        )
        results = [
            {
                "title":   r.get("title", ""),
                "url":     r.get("url", ""),
                "content": r.get("content", "")[:500],
                "score":   r.get("score", 0.0),
            }
            for r in response.get("results", [])
        ]
        return {
            "query":   query,
            "results": results,
            "n":       len(results),
        }
    except ImportError:
        return {
            "error": "tavily-python not installed. Run: pip install tavily-python",
            "query": query,
            "results": [],
        }
    except Exception as e:
        return {
            "error":   str(e),
            "query":   query,
            "results": [],
        }


register(
    name="web_search",
    description=(
        "Search the web for current information not available in the ESG report index. "
        "Use ONLY for: current market prices (EU ETS carbon price), breaking news, "
        "regulatory updates after 2024, or when retrieve() returns no relevant results. "
        "Do NOT use for information that should be in indexed reports."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Web search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results (default 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    fn=_web_search,
)
