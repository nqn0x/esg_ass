"""
esg_rag/agents/csrd_compliance_agent.py
----------------------------------------
CSRD compliance agent: fills one ESRS E1 datapoint at a time.

For each datapoint in the template:
  1. retrieve() evidence using the datapoint's search_query
  2. Extract the value, unit, page from the top hit
  3. Mark "not disclosed" if nothing found — never fabricate

Output JSON per datapoint:
  {esrs_id, value, unit, source_page, source_doc, confidence}

Model: strong (accuracy matters here)
max_iter: 6 (multiple retrieve calls expected)
"""

import esg_rag.albert as albert
from esg_rag.agents import AgentDefinition

CSRD_COMPLIANCE_AGENT = AgentDefinition(
    name="csrd_compliance",
    system_prompt=(
        "You are filling a CSRD ESRS E1 compliance form. "
        "For each datapoint you are given:\n\n"
        "1. Call retrieve() with the provided search_query and company filter.\n"
        "2. Extract the exact value and unit from the evidence.\n"
        "3. Note the page number as the source.\n"
        "4. If the evidence does not contain the value, mark it as 'not disclosed'.\n"
        "5. NEVER fabricate numbers. If unsure, mark as 'not disclosed'.\n\n"
        "Respond ONLY with this JSON (no other text):\n"
        '{"value": "...", "unit": "...", "source_page": 0, '
        '"source_text": "...", "confidence": 0.0}\n\n'
        "confidence: 0.9+ if number found verbatim, 0.6 if inferred, 0.0 if not disclosed.\n"
        "source_text: the exact sentence containing the value (max 150 chars)."
    ),
    allowed_tools=["retrieve", "read_table", "fetch_regulation"],
    model=albert.STRONG_MODEL,
    max_iterations=3,
)
