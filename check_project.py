"""
check_project.py
----------------
Full project health check. Run before submitting.

Usage:
    python check_project.py

Checks every major component and prints a clear pass/fail report.
Saves detailed results to docs/health_check.md
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

# ── Colour helpers ────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):  print(f"  {GREEN}✅ {msg}{RESET}")
def fail(msg):print(f"  {RED}❌ {msg}{RESET}")
def warn(msg):print(f"  {YELLOW}⚠️  {msg}{RESET}")
def info(msg):print(f"  {BLUE}ℹ️  {msg}{RESET}")

results = []  # (label, status, detail)

def check(label, fn):
    try:
        detail = fn()
        results.append((label, "pass", detail or ""))
        ok(f"{label}: {detail or 'OK'}")
        return True
    except Exception as e:
        detail = str(e)
        results.append((label, "fail", detail))
        fail(f"{label}: {detail[:120]}")
        return False

# ─────────────────────────────────────────────────────────────────────────────

print(f"\n{BOLD}{'='*60}")
print("  ESG Assistant — Pre-submission Health Check")
print(f"{'='*60}{RESET}\n")

# ── 1. File structure ─────────────────────────────────────────────────────────
print(f"{BOLD}[1/9] File Structure{RESET}")

required_files = [
    "esg_rag/__init__.py",
    "esg_rag/schemas.py",
    "esg_rag/albert.py",
    "esg_rag/parsing.py",
    "esg_rag/chunking.py",
    "esg_rag/chunk_quality.py",
    "esg_rag/contextual.py",
    "esg_rag/store.py",
    "esg_rag/ingest.py",
    "esg_rag/bm25_search.py",
    "esg_rag/dense_search.py",
    "esg_rag/fusion.py",
    "esg_rag/rerank.py",
    "esg_rag/router.py",
    "esg_rag/self_correct.py",
    "esg_rag/retrieve.py",
    "esg_rag/synthesize.py",
    "esg_rag/verifier.py",
    "esg_rag/agents/__init__.py",
    "esg_rag/agents/retriever_agent.py",
    "esg_rag/agents/analyst_agent.py",
    "esg_rag/agents/fact_checker_agent.py",
    "esg_rag/agents/lead_orchestrator.py",
    "esg_rag/tools/__init__.py",
    "esg_rag/tools/retrieve_tool.py",
    "esg_rag/tools/list_documents.py",
    "esg_rag/tools/read_table.py",
    "esg_rag/tools/compute.py",
    "esg_rag/tools/compare_documents.py",
    "esg_rag/tools/fetch_regulation.py",
    "esg_rag/tools/web_search.py",
    "esg_rag/tools/spawn_subagent.py",
    "esg_rag/eval/__init__.py",
    "esg_rag/eval/golden_set.csv",
    "esg_rag/eval/harness.py",
    "esg_rag/eval/plot_ablation.py",
    "components/__init__.py",
    "components/chat.py",
    "components/doc_library.py",
    "components/tool_trace.py",
    "components/citations.py",
    "components/compare_view.py",
    "components/cost_panel.py",
    "app.py",
    "pipeline_config.yaml",
    "ingest_manifest.yaml",
    ".env",
]

missing = [f for f in required_files if not Path(f).exists()]
if missing:
    for m in missing:
        fail(f"MISSING: {m}")
    results.append(("File structure", "fail", f"{len(missing)} files missing"))
else:
    ok(f"All {len(required_files)} required files present")
    results.append(("File structure", "pass", f"{len(required_files)} files"))

# ── 2. Environment ────────────────────────────────────────────────────────────
print(f"\n{BOLD}[2/9] Environment{RESET}")

check(".env loaded", lambda: (
    __import__('dotenv').load_dotenv() or
    f"ALBERT_BASE_URL={'set' if os.getenv('ALBERT_BASE_URL') else 'MISSING'}, "
    f"ALBERT_API_KEY={'set' if os.getenv('ALBERT_API_KEY') else 'MISSING'}"
))

from dotenv import load_dotenv
load_dotenv()

def check_env():
    missing_keys = [k for k in ["ALBERT_BASE_URL", "ALBERT_API_KEY"] if not os.getenv(k)]
    if missing_keys:
        raise ValueError(f"Missing env vars: {missing_keys}")
    return f"base_url={os.getenv('ALBERT_BASE_URL')}"
check("Environment variables", check_env)

# ── 3. Albert API ─────────────────────────────────────────────────────────────
print(f"\n{BOLD}[3/9] Albert API{RESET}")

def check_models():
    import esg_rag.albert as a
    models = a.list_models()
    return f"{len(models)} models available"
check("Albert list_models", check_models)

def check_embed():
    import esg_rag.albert as a
    vecs = a.embed_texts(["ESG Scope 1 emissions test"])
    return f"dim={len(vecs[0])}"
check("Albert embeddings", check_embed)

def check_chat():
    import esg_rag.albert as a
    resp = a.chat([{"role": "user", "content": "Reply with the single word: OK"}])
    text = resp["choices"][0]["message"]["content"]
    return f"reply='{text[:30]}'"
check("Albert chat", check_chat)

def check_rerank():
    import esg_rag.albert as a
    docs = ["Apple Scope 1 emissions 55000 tCO2e", "Paris weather today"]
    ranked = a.rerank("Apple emissions", docs)
    return f"top_score={ranked[0]['score']:.3f} top_idx={ranked[0]['index']}"
check("Albert rerank", check_rerank)

# ── 4. Qdrant Index ───────────────────────────────────────────────────────────
print(f"\n{BOLD}[4/9] Qdrant Index{RESET}")

def check_index():
    from esg_rag.store import get_store
    store = get_store()
    docs = store.list_docs()
    if not docs:
        raise ValueError("No documents indexed!")
    companies = sorted(set(d["company"] for d in docs))
    years     = sorted(set(d["year"]    for d in docs))
    chunks    = sum(d["n_chunks"] for d in docs)
    return f"{len(docs)} docs, {chunks:,} chunks, {len(companies)} companies, years={years}"
check("Qdrant index", check_index)

# ── 5. Retrieval pipeline ─────────────────────────────────────────────────────
print(f"\n{BOLD}[5/9] Retrieval Pipeline{RESET}")

def check_dense():
    from esg_rag.retrieve import retrieve
    r = retrieve("Apple Scope 1 GHG emissions")
    if not r.hits:
        raise ValueError("No hits returned")
    return f"{len(r.hits)} hits, top=[{r.hits[0].company} p.{r.hits[0].page}] score={r.hits[0].score:.3f}"
check("Dense retrieval", check_dense)

def check_router():
    from esg_rag.router import classify_query
    tests = {
        "What are Apple's Scope 1 emissions?":         "factual_lookup",
        "Compare Microsoft and Google water usage":     "cross_doc_compare",
        "What does ESRS E1 require?":                  "regulatory_check",
        "How did Tesla emissions change year over year": "numeric_computation",
    }
    wrong = []
    for q, expected in tests.items():
        got = classify_query(q).label
        if got != expected:
            wrong.append(f"'{q[:30]}' → {got} (expected {expected})")
    if wrong:
        raise ValueError("; ".join(wrong))
    return f"all {len(tests)} queries classified correctly"
check("Router classification", check_router)

def check_rerank_pipeline():
    import yaml
    from esg_rag.retrieve import retrieve
    cfg = yaml.safe_load(Path("pipeline_config.yaml").read_text())
    cfg["retrieval"]["use_reranker"] = True
    r = retrieve("Nike water reduction target", config=cfg)
    if not r.hits:
        raise ValueError("No hits")
    return f"{len(r.hits)} hits after reranking, top score={r.hits[0].score:.3f}"
check("Retrieval + reranker", check_rerank_pipeline)

# ── 6. Tools ──────────────────────────────────────────────────────────────────
print(f"\n{BOLD}[6/9] Tools{RESET}")

def load_tools():
    import yaml
    from esg_rag.tools import load_all, TOOLS
    cfg = yaml.safe_load(Path("pipeline_config.yaml").read_text())
    cfg["agent"]["tools"]["compare_documents"] = True
    cfg["agent"]["tools"]["fetch_regulation"]  = True
    load_all(cfg)
    return list(TOOLS.keys())

tools = None
def check_tools_load():
    global tools
    tools = load_tools()
    return f"{len(tools)} tools: {', '.join(tools)}"
check("Tools registry", check_tools_load)

def check_compute():
    from esg_rag.tools import call_tool
    if tools is None: load_tools()
    r = call_tool("compute", {"expression": "(55200 - 47430) / 47430 * 100"})
    if "error" in r: raise ValueError(r["error"])
    return f"result={r['formatted']}"
check("compute tool", check_compute)

def check_list_docs_tool():
    from esg_rag.tools import call_tool
    if tools is None: load_tools()
    r = call_tool("list_documents", {})
    return f"{r['total_docs']} docs, {r['total_chunks']:,} chunks"
check("list_documents tool", check_list_docs_tool)

def check_fetch_reg():
    from esg_rag.tools import call_tool
    if tools is None: load_tools()
    r = call_tool("fetch_regulation", {"regulation_id": "csrd"})
    if "error" in r: raise ValueError(r["error"])
    return f"content={len(r['content'])} chars"
check("fetch_regulation tool", check_fetch_reg)

def check_retrieve_tool():
    from esg_rag.tools import call_tool
    if tools is None: load_tools()
    r = call_tool("retrieve", {"query": "Apple carbon neutral goal", "filters": {"company": "Apple"}})
    return f"{r['n_hits']} hits, class={r['query_class']}"
check("retrieve tool", check_retrieve_tool)

# ── 7. Synthesis ──────────────────────────────────────────────────────────────
print(f"\n{BOLD}[7/9] Synthesis + Verifier{RESET}")

def check_synthesis():
    from esg_rag.synthesize import answer_question
    r = answer_question("What are Apple's Scope 1 emissions?", filters={"company": "Apple"})
    if not r["answer"] or r["answer"].startswith("[synthesis error"):
        raise ValueError(f"Bad answer: {r['answer'][:100]}")
    verdict = r["verifier_result"]["verdict"]
    return f"answer={r['answer'][:80]}… verdict={verdict}"
check("answer_question (simple)", check_synthesis)

def check_verifier():
    from esg_rag.verifier import verify_claims
    answer = "Apple's Scope 1 emissions were 55,200 tCO2e in 2022."
    contexts = ["Apple Scope 1 gross emissions 55,200 metric tons CO2e fiscal year 2022"]
    r = verify_claims(answer, contexts)
    return f"verdict={r['verdict']}, claims={r['n_claims_checked']}"
check("Verifier", check_verifier)

# ── 8. Eval harness ───────────────────────────────────────────────────────────
print(f"\n{BOLD}[8/9] Eval Harness{RESET}")

def check_golden_set():
    import csv
    rows = list(csv.DictReader(open("esg_rag/eval/golden_set.csv")))
    types = set(r["question_type"] for r in rows)
    return f"{len(rows)} questions, types={sorted(types)}"
check("Golden set", check_golden_set)

def check_scoreboard():
    sb = Path("esg_rag/eval/scoreboard.csv")
    if not sb.exists():
        raise ValueError("scoreboard.csv missing — run harness first")
    import csv
    rows = list(csv.DictReader(open(sb)))
    if not rows:
        raise ValueError("Scoreboard is empty")
    labels = [r["label"] for r in rows]
    best = max(rows, key=lambda r: float(r.get("faithfulness") or 0))
    return (f"{len(rows)} runs: {labels} | "
            f"best={best['label']} faith={float(best.get('faithfulness',0)):.3f}")
check("Scoreboard", check_scoreboard)

def check_ablation_chart():
    p = Path("docs/ablation.png")
    if not p.exists():
        raise ValueError("docs/ablation.png missing — run plot_ablation.py")
    size_kb = p.stat().st_size // 1024
    return f"exists ({size_kb}KB)"
check("Ablation chart", check_ablation_chart)

# ── 9. Streamlit imports ──────────────────────────────────────────────────────
print(f"\n{BOLD}[9/9] Streamlit App{RESET}")

def check_streamlit_imports():
    import importlib.util
    comps = ["components.chat", "components.doc_library",
             "components.tool_trace", "components.citations",
             "components.compare_view", "components.cost_panel"]
    for comp in comps:
        spec = importlib.util.find_spec(comp)
        if spec is None:
            raise ImportError(f"Cannot find {comp}")
    return f"all {len(comps)} components importable"
check("Streamlit components", check_streamlit_imports)

def check_app_syntax():
    import ast
    code = Path("app.py").read_text()
    ast.parse(code)
    return "app.py syntax OK"
check("app.py syntax", check_app_syntax)

# ── Final report ──────────────────────────────────────────────────────────────

passed = [r for r in results if r[1] == "pass"]
failed = [r for r in results if r[1] == "fail"]

print(f"\n{BOLD}{'='*60}")
print(f"  RESULTS: {len(passed)}/{len(results)} checks passed")
print(f"{'='*60}{RESET}")

if failed:
    print(f"\n{RED}{BOLD}Failed checks:{RESET}")
    for label, _, detail in failed:
        print(f"  ❌ {label}: {detail[:100]}")
else:
    print(f"\n{GREEN}{BOLD}All checks passed! Ready to submit. 🎉{RESET}")

# ── Save report ───────────────────────────────────────────────────────────────
Path("docs").mkdir(exist_ok=True)
report_lines = [
    "# ESG Assistant — Health Check Report\n",
    f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n",
    f"**{len(passed)}/{len(results)} checks passed**\n\n",
    "| Check | Status | Detail |\n",
    "|-------|--------|--------|\n",
]
for label, status, detail in results:
    icon = "✅" if status == "pass" else "❌"
    report_lines.append(f"| {label} | {icon} | {str(detail)[:80]} |\n")

Path("docs/health_check.md").write_text("".join(report_lines))
print(f"\n  Report saved → docs/health_check.md")

if failed:
    sys.exit(1)
