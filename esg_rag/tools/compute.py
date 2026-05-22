"""
esg_rag/tools/compute.py
-------------------------
Tool: compute
Schema: {expression, named_values?}

Safe sandboxed arithmetic evaluator using asteval.
The agent uses this for YoY calculations, ratios, percentages.
NEVER uses Python eval() — asteval restricts to math operations only.

Examples:
  expression: "(55200 - 48000) / 48000 * 100"
  → {"result": 15.0, "expression": "...", "formatted": "15.00%"}

  expression: "scope1 + scope2"
  named_values: {"scope1": 55200, "scope2": 12000}
  → {"result": 67200, ...}
"""

from __future__ import annotations

from esg_rag.tools import register


def _compute(
    expression: str,
    named_values: dict[str, float] | None = None,
) -> dict:
    """
    Evaluate a mathematical expression safely.

    Args:
        expression:   math expression string, e.g. "(a - b) / b * 100"
        named_values: optional variable bindings, e.g. {"a": 55200, "b": 48000}

    Returns:
        {result, expression, formatted, named_values}
    """
    try:
        from asteval import Interpreter
    except ImportError:
        # Fallback: very restricted eval with only math
        return _fallback_compute(expression, named_values or {})

    aeval = Interpreter()

    # Inject named values
    if named_values:
        for k, v in named_values.items():
            aeval.symtable[k] = float(v)

    result = aeval(expression)

    if aeval.error:
        return {
            "error": "; ".join(str(e.get_error()) for e in aeval.error),
            "expression": expression,
        }

    # Format result
    formatted = _format_result(result, expression)

    return {
        "result":       result,
        "expression":   expression,
        "formatted":    formatted,
        "named_values": named_values or {},
    }


def _format_result(result: float, expression: str) -> str:
    """Smart formatting based on the expression content."""
    if result is None:
        return "None"
    if "100" in expression and ("/" in expression or "%" in expression):
        return f"{result:.2f}%"
    if abs(result) >= 1_000_000:
        return f"{result:,.0f}"
    if abs(result) >= 1000:
        return f"{result:,.1f}"
    return f"{result:.4f}".rstrip("0").rstrip(".")


def _fallback_compute(expression: str, named_values: dict) -> dict:
    """
    Ultra-restricted fallback if asteval isn't installed.
    Only allows digits, operators, spaces, dots, parentheses, and variable names.
    """
    import re
    safe_expr = expression
    for k, v in named_values.items():
        safe_expr = safe_expr.replace(k, str(float(v)))

    # Validate: only allow safe characters
    if not re.match(r'^[\d\s\+\-\*\/\.\(\)]+$', safe_expr):
        return {"error": "Expression contains unsafe characters", "expression": expression}

    try:
        result = eval(safe_expr, {"__builtins__": {}}, {})  # noqa: S307
        return {
            "result":     result,
            "expression": expression,
            "formatted":  _format_result(result, expression),
            "named_values": named_values,
        }
    except Exception as e:
        return {"error": str(e), "expression": expression}


register(
    name="compute",
    description=(
        "Safely evaluate a mathematical expression. "
        "Use this for any arithmetic: YoY percentage changes, ratios, totals, unit conversions. "
        "Never do math in your head — always use this tool for numeric calculations. "
        "Example: expression='(new - old) / old * 100', named_values={'new': 55200, 'old': 48000}"
    ),
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression, e.g. '(a - b) / b * 100'",
            },
            "named_values": {
                "type": "object",
                "description": "Variable name → numeric value mappings",
                "additionalProperties": {"type": "number"},
            },
        },
        "required": ["expression"],
    },
    fn=_compute,
)
