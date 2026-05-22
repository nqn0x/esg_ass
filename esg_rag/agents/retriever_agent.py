"""
esg_rag/agents/retriever_agent.py
----------------------------------
Retriever agent: finds evidence, doesn't write the final answer.
Tools: retrieve, list_documents
Model: cheap (fast, many iterations expected)
"""

from esg_rag.agents import AgentDefinition

RETRIEVER_AGENT = AgentDefinition(
    name="retriever",
    system_prompt=(
        "You are an ESG evidence retrieval specialist. "
        "Your job is to find relevant evidence from indexed sustainability reports. "
        "Strategy:\n"
        "1. Call list_documents() if unsure what's indexed.\n"
        "2. Call retrieve() with a specific query. Try keyword-style queries for BM25 "
        "   AND conceptual queries for semantic search.\n"
        "3. If first retrieve() returns weak results, try rephrasing with different keywords.\n"
        "4. Use filters {company, year} to scope searches.\n"
        "5. Return a summary of the evidence found — page numbers, key metrics, source companies.\n"
        "Do NOT write a final answer. Only summarise what you found."
    ),
    allowed_tools=["retrieve", "list_documents"],
    max_iterations=3,
)
