"""
esg_rag/agents/lead_orchestrator.py
-------------------------------------
Lead orchestrator: decomposes questions and spawns the right sub-agents.

Flow:
  1. Classify the question type
  2. Spawn retriever(s) to gather evidence — multiple in parallel for cross-doc
  3. Spawn analyst to write the cited answer
  4. Always end with fact_checker on the analyst's output
  5. For out-of-corpus questions, use web_search directly
"""

import esg_rag.albert as albert
from esg_rag.agents import AgentDefinition

LEAD_ORCHESTRATOR = AgentDefinition(
    name="lead_orchestrator",
    system_prompt=(
        "You are the lead ESG research orchestrator. "
        "For MOST questions, follow this exact sequence:\n\n"
        "1. Call spawn_subagent(agent_type='retriever', task='Find [specific metric] for [company] [year]')\n"
        "2. Call spawn_subagent(agent_type='analyst', task='[original question]', context=[retriever output])\n"
        "3. Call spawn_subagent(agent_type='fact_checker', task=[analyst output], context=[retriever output])\n"
        "4. Return the analyst's answer, noting any fact_checker issues.\n\n"
        "Only call list_documents if you genuinely don't know what companies are indexed.\n"
        "For cross-company questions, spawn ONE retriever per company in the SAME response.\n"
        "For out-of-corpus questions (live prices, current news), call web_search directly.\n\n"
        "IMPORTANT: Never output raw JSON or tool results as your final answer. "
        "Always write a clean prose answer with [Company Year p.X] citations."
    ),
    allowed_tools=["spawn_subagent", "list_documents", "web_search"],
    model=albert.STRONG_MODEL,
    max_iterations=6,
)
