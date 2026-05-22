"""
esg_rag/agents/__init__.py
--------------------------
Base agent runner used by every agent in the system.

run_agent(agent_def, task, context) -> AgentResult

Loop:
  1. Build messages (system + history)
  2. Call albert.chat() with allowed tools
  3. If response has tool_calls → execute in parallel via asyncio.gather
  4. Append tool results → repeat
  5. Stop when no tool_calls or max_iterations reached

ReAct JSON fallback:
  If Albert's model doesn't support native tool calling (detected from
  docs/albert_capabilities.md), the loop switches to ReAct:
  the model outputs {"action": "tool_name", "action_input": {...}}
  and we parse + execute manually.

AgentDefinition: name, system_prompt, allowed_tools, model, max_iterations
AgentResult: final_output, tool_trace, iterations_used, tokens, retrieved_contexts
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import esg_rag.albert as albert
from esg_rag.schemas import AgentResult, SearchHit
from esg_rag.tools import TOOLS, call_tool, to_openai_schema


# ── AgentDefinition ───────────────────────────────────────────────────────────

@dataclass
class AgentDefinition:
    name:          str
    system_prompt: str
    allowed_tools: list[str]
    model:         str = albert.CHAT_MODEL
    max_iterations: int = 4


# ── Detect native tool support ────────────────────────────────────────────────

def _has_native_tools() -> bool:
    """
    Check docs/albert_capabilities.md for native tool support.
    Falls back to False if file doesn't exist (use ReAct).
    """
    cap_path = Path("docs/albert_capabilities.md")
    if cap_path.exists():
        content = cap_path.read_text()
        return "native_tools=YES" in content
    return False


NATIVE_TOOLS = _has_native_tools()


# ── Tool execution ────────────────────────────────────────────────────────────

async def _execute_tool_async(name: str, args: dict) -> tuple[str, Any, float]:
    """Execute a single tool call asynchronously. Returns (name, result, latency_ms)."""
    loop = asyncio.get_event_loop()
    t0 = time.perf_counter()
    try:
        result = await loop.run_in_executor(None, lambda: call_tool(name, args))
    except Exception as e:
        result = {"error": str(e)}
    latency = (time.perf_counter() - t0) * 1000
    return name, result, latency


async def _execute_tools_parallel(
    tool_calls: list[dict],
) -> list[dict]:
    """Execute multiple tool calls in parallel. Returns list of {name, result, latency_ms}."""
    tasks = []
    for tc in tool_calls:
        name = tc["name"]
        args = tc["args"]
        if name not in TOOLS:
            tasks.append(_execute_tool_async("__unknown__", {"tool": name}))
        else:
            tasks.append(_execute_tool_async(name, args))

    results = await asyncio.gather(*tasks)
    return [
        {"name": name, "result": result, "latency_ms": round(latency, 1)}
        for name, result, latency in results
    ]


# ── ReAct parser ─────────────────────────────────────────────────────────────

_REACT_RE = re.compile(
    r'\{[^{}]*"action"\s*:\s*"([^"]+)"[^{}]*"action_input"\s*:\s*(\{[^}]*\}|\[[^\]]*\]|"[^"]*"|\d+|true|false|null)[^{}]*\}',
    re.DOTALL,
)


def _parse_react(text: str) -> list[dict] | None:
    """
    Parse ReAct-style JSON action from model output.
    Returns list of {name, args} or None if no action found.
    """
    # Try the full JSON block first
    match = _REACT_RE.search(text)
    if match:
        try:
            # Find the full JSON object
            start = text.rfind("{", 0, match.start() + 1)
            blob = text[match.start():].split("\n\n")[0]
            data = json.loads(blob)
            return [{"name": data["action"], "args": data.get("action_input", {})}]
        except Exception:
            pass

    # Try code blocks
    for block in re.findall(r"```(?:json)?\s*([\s\S]+?)```", text):
        try:
            data = json.loads(block.strip())
            if "action" in data:
                args = data.get("action_input", {})
                if isinstance(args, str):
                    args = {"query": args}
                return [{"name": data["action"], "args": args}]
        except Exception:
            continue

    return None


def _build_react_system(agent_def: AgentDefinition) -> str:
    """Extend system prompt with ReAct instructions."""
    tool_descs = "\n".join(
        f"- {name}: {TOOLS[name]['description']}"
        for name in agent_def.allowed_tools
        if name in TOOLS
    )
    return (
        agent_def.system_prompt + "\n\n"
        "## Tool Use Instructions\n"
        "You have access to these tools:\n"
        f"{tool_descs}\n\n"
        "To use a tool, output ONLY this JSON (no other text before it):\n"
        '{"action": "tool_name", "action_input": {"arg": "value"}}\n\n'
        "After receiving tool results, continue reasoning.\n"
        "When you have enough information, output your final answer as plain text "
        "(no JSON, no action key).\n"
        "Never fabricate tool results."
    )


# ── Main run_agent ────────────────────────────────────────────────────────────

def run_agent(
    agent_def: AgentDefinition,
    task: str,
    context: dict | None = None,
) -> AgentResult:
    """
    Run an agent loop until it produces a final answer or hits max_iterations.

    Args:
        agent_def: agent configuration
        task:      user task / question
        context:   optional extra context (prior evidence, etc.)

    Returns:
        AgentResult with final_output, tool_trace, iterations_used
    """
    context = context or {}
    tool_trace: list[dict] = []
    retrieved_contexts: list[SearchHit] = []
    tokens_in = 0
    tokens_out = 0

    # Build allowed tools schema
    allowed_schemas = [
        s for s in to_openai_schema()
        if s["function"]["name"] in agent_def.allowed_tools
    ]

    # Build initial messages
    system = (
        _build_react_system(agent_def)
        if not NATIVE_TOOLS
        else agent_def.system_prompt
    )

    messages: list[dict] = [{"role": "system", "content": system}]

    # Inject context if provided
    if context.get("evidence"):
        messages.append({
            "role": "user",
            "content": f"Background evidence:\n{context['evidence']}\n\nTask: {task}",
        })
    else:
        messages.append({"role": "user", "content": task})

    final_output = ""

    for iteration in range(agent_def.max_iterations):
        # ── Call Albert ───────────────────────────────────────────────────────
        try:
            if NATIVE_TOOLS and allowed_schemas:
                resp = albert.chat(
                    messages,
                    tools=allowed_schemas,
                    model=agent_def.model,
                    max_tokens=1024,
                    caller=f"agent_{agent_def.name}",
                )
            else:
                resp = albert.chat(
                    messages,
                    model=agent_def.model,
                    max_tokens=1024,
                    caller=f"agent_{agent_def.name}",
                )
        except Exception as e:
            final_output = f"[agent error: {e}]"
            break

        usage = resp.get("usage", {})
        tokens_in  += usage.get("prompt_tokens", 0)
        tokens_out += usage.get("completion_tokens", 0)

        msg = resp["choices"][0]["message"]
        # For native tools: preserve the full message including tool_calls array
        if NATIVE_TOOLS and msg.get("tool_calls"):
            messages.append(msg)  # keep the full assistant message
        else:
            messages.append({"role": "assistant", "content": msg.get("content") or ""})

        # ── Extract tool calls ────────────────────────────────────────────────
        tool_calls: list[dict] = []

        if NATIVE_TOOLS and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except Exception:
                    args = {}
                tool_calls.append({"id": tc.get("id", ""), "name": fn["name"], "args": args})
        elif not NATIVE_TOOLS:
            content = msg.get("content", "")
            parsed = _parse_react(content)
            if parsed:
                tool_calls = [{"id": f"react_{i}", **tc} for i, tc in enumerate(parsed)]

        # ── No tool calls → final answer ──────────────────────────────────────
        if not tool_calls:
            final_output = msg.get("content", "").strip()
            break

        # ── Execute tools in parallel ─────────────────────────────────────────
        exec_results = asyncio.run(_execute_tools_parallel(tool_calls))

        for tc, exec_r in zip(tool_calls, exec_results):
            result_str = json.dumps(exec_r["result"], ensure_ascii=False, default=str)

            # Record trace
            trace_entry = {
                "tool":       tc["name"],
                "args":       tc["args"],
                "result":     exec_r["result"],
                "latency_ms": exec_r["latency_ms"],
                "iteration":  iteration + 1,
            }
            tool_trace.append(trace_entry)

            # Collect retrieved contexts
            if tc["name"] == "retrieve" and isinstance(exec_r["result"], dict):
                for h in exec_r["result"].get("hits", []):
                    # Reconstruct a minimal SearchHit-like object
                    retrieved_contexts.append(h)  # type: ignore

            # Append tool result to messages
            if NATIVE_TOOLS:
                messages.append({
                    "role":        "tool",
                    "tool_call_id": tc["id"],
                    "content":     result_str[:4000],
                })
            else:
                messages.append({
                    "role":    "user",
                    "content": f"Tool result for {tc['name']}:\n{result_str[:4000]}",
                })

    # If loop exhausted without a final answer
    if not final_output:
        last = messages[-1].get("content", "")
        final_output = last if last else "[Agent reached max iterations without a final answer]"

    return AgentResult(
        final_output=final_output,
        tool_trace=tool_trace,
        iterations_used=iteration + 1,
        tokens={"in": tokens_in, "out": tokens_out},
        retrieved_contexts=retrieved_contexts,
    )
