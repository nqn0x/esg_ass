"""
esg_rag/tools/spawn_subagent.py
---------------------------------
Tool: spawn_subagent
Schema: {agent_type: retriever|analyst|fact_checker|csrd, task}

The orchestrator uses this to delegate sub-tasks to specialist agents.
Each call runs a full agent loop and returns {final_output, tool_trace_summary, iterations}.
"""

from __future__ import annotations

from esg_rag.tools import register


def _spawn_subagent(agent_type: str, task: str, context: str = "") -> dict:
    """
    Spawn a specialist sub-agent to handle a specific task.

    agent_type options:
      retriever    — find evidence from the index
      analyst      — write a cited answer from evidence
      fact_checker — verify claims against retrieved evidence

    Returns the agent's final output and a trace summary.
    """
    from esg_rag.agents import run_agent
    from esg_rag.agents.retriever_agent   import RETRIEVER_AGENT
    from esg_rag.agents.analyst_agent     import ANALYST_AGENT
    from esg_rag.agents.fact_checker_agent import FACT_CHECKER_AGENT

    agents = {
        "retriever":    RETRIEVER_AGENT,
        "analyst":      ANALYST_AGENT,
        "fact_checker": FACT_CHECKER_AGENT,
    }

    if agent_type not in agents:
        return {
            "error": f"Unknown agent_type '{agent_type}'. Use: {list(agents.keys())}",
        }

    agent_def = agents[agent_type]
    ctx = {"evidence": context} if context else {}

    result = run_agent(agent_def, task, context=ctx)

    return {
        "agent_type":        agent_type,
        "final_output":      result.final_output,
        "iterations_used":   result.iterations_used,
        "tool_trace_summary": [
            {"tool": t["tool"], "latency_ms": t["latency_ms"]}
            for t in result.tool_trace
        ],
        "tokens": result.tokens,
    }


register(
    name="spawn_subagent",
    description=(
        "Delegate a task to a specialist sub-agent. "
        "Use retriever to find evidence, analyst to write cited answers, "
        "fact_checker to verify claims. "
        "For cross-document comparisons, spawn multiple retriever agents in parallel "
        "by calling this tool multiple times in the same response."
    ),
    parameters={
        "type": "object",
        "properties": {
            "agent_type": {
                "type": "string",
                "enum": ["retriever", "analyst", "fact_checker"],
                "description": "Which specialist agent to run",
            },
            "task": {
                "type": "string",
                "description": "Specific task for the sub-agent, e.g. 'Find Apple Scope 1 emissions 2023'",
            },
            "context": {
                "type": "string",
                "description": "Optional background context to pass to the agent",
                "default": "",
            },
        },
        "required": ["agent_type", "task"],
    },
    fn=_spawn_subagent,
)
