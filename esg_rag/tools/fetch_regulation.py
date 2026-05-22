"""
esg_rag/tools/fetch_regulation.py
----------------------------------
Tool: fetch_regulation
Schema: {regulation_id}

Reads pre-cached regulation markdown from data/regulations/{id}.md
Pre-cache one-time: CSRD, ESRS E1-E5, S1-S4, G1, EU Taxonomy, GRI, TCFD, SASB.

If the file doesn't exist, returns a summary from memory.
"""

from __future__ import annotations

from pathlib import Path

from esg_rag.tools import register

REGULATIONS_DIR = Path("data/regulations")
REGULATIONS_DIR.mkdir(parents=True, exist_ok=True)

# Built-in summaries for when markdown files aren't cached yet
BUILTIN_SUMMARIES = {
    "csrd": """# CSRD — Corporate Sustainability Reporting Directive
The CSRD (EU 2022/2464) requires large EU companies to report on sustainability matters using ESRS.
Key requirements:
- Mandatory use of European Sustainability Reporting Standards (ESRS)
- Double materiality assessment (financial + impact materiality)
- Independent limited assurance of sustainability information
- Machine-readable format (XBRL/iXBRL tagging)
- In-scope: EU companies with 250+ employees or €40M+ turnover
- Phased timeline: FY2024 (large listed), FY2025 (large non-listed), FY2026 (listed SMEs)""",

    "esrs_e1": """# ESRS E1 — Climate Change
Covers climate-related transition plans, physical and transition risks, and GHG emissions.
Key disclosures:
- E1-1: Transition plan for climate change mitigation
- E1-2: Policies related to climate change
- E1-3: Actions and resources for climate change
- E1-4: Targets related to climate change
- E1-5: Energy consumption and mix
- E1-6: GHG emissions (Scope 1, 2, 3) in tCO2e
- E1-7: GHG removals and carbon credits
- E1-9: Financial effects of climate-related risks""",

    "tcfd": """# TCFD — Task Force on Climate-related Financial Disclosures
Four pillars:
1. Governance: Board and management oversight of climate risks
2. Strategy: Climate risks/opportunities and their financial impacts
3. Risk Management: Processes for identifying and managing climate risks
4. Metrics & Targets: GHG emissions (Scope 1, 2, 3), climate targets, internal carbon price""",

    "gri": """# GRI Standards — Global Reporting Initiative
Universal Standards (GRI 1, 2, 3) apply to all organizations.
Topic Standards cover specific ESG areas:
- GRI 302: Energy
- GRI 303: Water and Effluents
- GRI 305: Emissions (Scope 1, 2, 3)
- GRI 306: Waste
- GRI 401: Employment
- GRI 405: Diversity and Equal Opportunity""",

    "sbti": """# SBTi — Science Based Targets initiative
Requirements for corporate net-zero targets:
- Near-term targets: reduce Scope 1+2 by 50%+ by 2030 (from 2020 base)
- Long-term targets: reduce Scope 1+2+3 by 90%+ by 2050
- Remaining emissions offset by carbon removals only
- Scope 3 must be included if >40% of total emissions
- Validated and approved by SBTi expert panel""",

    "eu_taxonomy": """# EU Taxonomy Regulation
Classification system for environmentally sustainable economic activities.
Six environmental objectives:
1. Climate change mitigation
2. Climate change adaptation
3. Sustainable use of water
4. Circular economy transition
5. Pollution prevention
6. Biodiversity protection
Activities must meet DNSH (Do No Significant Harm) criteria and minimum social safeguards.""",
}


def _fetch_regulation(regulation_id: str) -> dict:
    """
    Fetch regulation text by ID.
    Checks data/regulations/ first, falls back to built-in summaries.
    """
    reg_id = regulation_id.lower().replace(" ", "_").replace("-", "_")

    # Try cached markdown file
    md_path = REGULATIONS_DIR / f"{reg_id}.md"
    if md_path.exists():
        content = md_path.read_text(encoding="utf-8")
        return {
            "regulation_id": regulation_id,
            "content":       content,
            "source":        "cached_file",
            "path":          str(md_path),
        }

    # Fall back to built-in summary
    for key, summary in BUILTIN_SUMMARIES.items():
        if key in reg_id or reg_id in key:
            return {
                "regulation_id": regulation_id,
                "content":       summary,
                "source":        "builtin_summary",
            }

    return {
        "regulation_id": regulation_id,
        "error": f"Regulation '{regulation_id}' not found. "
                 f"Available: {list(BUILTIN_SUMMARIES.keys())}. "
                 f"Add a markdown file to data/regulations/{reg_id}.md to cache it.",
    }


register(
    name="fetch_regulation",
    description=(
        "Fetch the text of an ESG regulation or reporting standard. "
        "Use this to answer questions about CSRD, ESRS, TCFD, GRI, SBTi, EU Taxonomy requirements. "
        "Available IDs: csrd, esrs_e1, tcfd, gri, sbti, eu_taxonomy"
    ),
    parameters={
        "type": "object",
        "properties": {
            "regulation_id": {
                "type": "string",
                "description": "Regulation identifier, e.g. 'csrd', 'esrs_e1', 'tcfd', 'gri', 'sbti'",
            },
        },
        "required": ["regulation_id"],
    },
    fn=_fetch_regulation,
)
