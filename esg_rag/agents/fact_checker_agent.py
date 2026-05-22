"""
esg_rag/agents/fact_checker_agent.py
--------------------------------------
Fact checker: verifies claims in the analyst's answer against retrieved evidence.
Tools: retrieve (read-only re-check)
Model: medium
Output JSON: {verdict: pass|fail, issues: [{claim, severity, reason}]}
"""

import esg_rag.albert as albert
from esg_rag.agents import AgentDefinition

FACT_CHECKER_AGENT = AgentDefinition(
    name="fact_checker",
    system_prompt=(
        "Your job is to break this answer, not confirm it. "
        "For each numeric claim or specific fact in the answer:\n"
        "1. Use retrieve() to find the source chunk.\n"
        "2. Check if the number appears verbatim in the retrieved text.\n"
        "3. Flag any claim that is not directly supported.\n\n"
        "Output ONLY this JSON (no other text):\n"
        '{"verdict": "pass" | "fail", '
        '"issues": [{"claim": "...", "severity": "high|medium|low", "reason": "..."}]}\n\n'
        "verdict=pass means all key claims are supported.\n"
        "verdict=fail means at least one high-severity issue was found.\n"
        "Be strict: vague paraphrasing is not the same as verbatim support."
    ),
    allowed_tools=["retrieve"],
    model=albert.CHAT_MODEL,
    max_iterations=2,
)
