"""
esg_rag/eval/harness.py
-----------------------
evaluate(pipeline_fn, label, golden_path) -> dict

Runs a pipeline function against the golden set and records results
in esg_rag/eval/scoreboard.csv.

pipeline_fn signature:
    pipeline_fn(question: str, filters: dict) -> {
        "answer": str,
        "retrieved_contexts": list[str],   # text of retrieved chunks
        "telemetry": dict,                 # latency_ms, etc.
    }

Metrics (via RAGAS with Albert as LLM):
    faithfulness        — is the answer grounded in the contexts?
    answer_relevancy    — is the answer relevant to the question?
    context_precision   — are retrieved contexts ranked correctly?
    context_recall      — do contexts cover the ground truth?

Scoreboard columns:
    config_id, label, faithfulness, answer_relevancy,
    context_precision, context_recall,
    faithfulness_by_class, context_precision_by_class (JSON),
    avg_albert_calls, avg_latency_ms, n_questions, timestamp

Usage:
    python -m esg_rag.eval.harness --label v01_dense_only
    python -m esg_rag.eval.harness --label v02_hybrid --config pipeline_config.yaml
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import yaml
from dotenv import load_dotenv

load_dotenv()

GOLDEN_PATH  = Path("esg_rag/eval/golden_set.csv")
SCOREBOARD   = Path("esg_rag/eval/scoreboard.csv")
SCOREBOARD.parent.mkdir(parents=True, exist_ok=True)

# ── RAGAS setup with Albert ───────────────────────────────────────────────────

def _build_ragas_llm():
    try:
        from openai import OpenAI
        from ragas.llms import llm_factory
        client = OpenAI(
            base_url=os.environ["ALBERT_BASE_URL"] + "/v1",
            api_key=os.environ["ALBERT_API_KEY"],
        )
        model = os.getenv("ALBERT_CHAT_MODEL", "mistralai/Ministral-3-8B-Instruct-2512")
        return llm_factory(model, client=client)
    except Exception as e:
        print(f"  [harness] RAGAS LLM setup failed: {e}")
        return None


def _build_ragas_embeddings():
    try:
        from openai import OpenAI
        from ragas.embeddings import embedding_factory
        client = OpenAI(
            base_url=os.environ["ALBERT_BASE_URL"] + "/v1",
            api_key=os.environ["ALBERT_API_KEY"],
        )
        model = os.getenv("ALBERT_EMBED_MODEL", "BAAI/bge-m3")
        return embedding_factory("openai", model=model, client=client)
    except Exception as e:
        print(f"  [harness] RAGAS embeddings setup failed: {e}")
        return None


def _run_ragas(questions, answers, contexts, ground_truths):
    try:
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics.collections import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )
        from datasets import Dataset

        ragas_llm = _build_ragas_llm()
        ragas_emb = _build_ragas_embeddings()

        metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
        if ragas_llm:
            for m in metrics:
                if hasattr(m, "llm"):
                    m.llm = ragas_llm
        if ragas_emb:
            for m in metrics:
                if hasattr(m, "embeddings"):
                    m.embeddings = ragas_emb

        dataset = Dataset.from_dict({
            "question":     questions,
            "answer":       answers,
            "contexts":     contexts,
            "ground_truth": ground_truths,
        })

        result = ragas_evaluate(dataset, metrics=metrics)
        df = result.to_pandas()

        return {
            "faithfulness":      round(float(df["faithfulness"].mean()),      4),
            "answer_relevancy":  round(float(df["answer_relevancy"].mean()),  4),
            "context_precision": round(float(df["context_precision"].mean()), 4),
            "context_recall":    round(float(df["context_recall"].mean()),    4),
            "_per_row": df[["faithfulness", "answer_relevancy",
                             "context_precision", "context_recall"]].to_dict("records"),
        }
    except Exception as e:
        print(f"  [harness] RAGAS failed ({e}) — using heuristic metrics")
        return _heuristic_metrics(questions, answers, contexts, ground_truths)

def _heuristic_metrics(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
) -> dict[str, float]:
    """
    Simple heuristic metrics that don't require RAGAS.
    Not as accurate but useful when RAGAS isn't available.

    faithfulness:       fraction of answer sentences that overlap with any context
    answer_relevancy:   token overlap between question and answer
    context_precision:  fraction of contexts that overlap with ground truth
    context_recall:     fraction of ground truth tokens found in any context
    """
    import re

    def tokens(text: str) -> set[str]:
        return set(re.findall(r'\b\w+\b', text.lower()))

    rows = []
    for q, a, ctx_list, gt in zip(questions, answers, contexts, ground_truths):
        ctx_tokens = set()
        for c in ctx_list:
            ctx_tokens |= tokens(c)

        a_sents = [s.strip() for s in re.split(r'[.!?]', a) if len(s.strip()) > 10]
        faith = (
            sum(1 for s in a_sents if tokens(s) & ctx_tokens) / len(a_sents)
            if a_sents else 0.0
        )

        q_tok = tokens(q)
        a_tok = tokens(a)
        relevancy = len(q_tok & a_tok) / len(q_tok) if q_tok else 0.0

        gt_tok = tokens(gt)
        prec_hits = [1 if tokens(c) & gt_tok else 0 for c in ctx_list]
        precision = sum(prec_hits) / len(prec_hits) if prec_hits else 0.0
        recall = len(gt_tok & ctx_tokens) / len(gt_tok) if gt_tok else 0.0

        rows.append({
            "faithfulness":      round(faith, 4),
            "answer_relevancy":  round(relevancy, 4),
            "context_precision": round(precision, 4),
            "context_recall":    round(recall, 4),
        })

    avg = lambda key: round(sum(r[key] for r in rows) / len(rows), 4) if rows else 0.0
    return {
        "faithfulness":      avg("faithfulness"),
        "answer_relevancy":  avg("answer_relevancy"),
        "context_precision": avg("context_precision"),
        "context_recall":    avg("context_recall"),
        "_per_row":          rows,
    }


# ── Golden set loader ─────────────────────────────────────────────────────────

def load_golden_set(path: Path = GOLDEN_PATH) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                row["doc_filter"] = json.loads(row["doc_filter"]) if row["doc_filter"] else {}
            except Exception:
                row["doc_filter"] = {}
            rows.append(row)
    return rows


# ── Scoreboard ────────────────────────────────────────────────────────────────

SCOREBOARD_COLS = [
    "config_id", "label", "timestamp",
    "faithfulness", "answer_relevancy", "context_precision", "context_recall",
    "faithfulness_by_class", "context_precision_by_class",
    "avg_albert_calls", "avg_latency_ms", "n_questions",
]


def _append_scoreboard(row: dict) -> None:
    write_header = not SCOREBOARD.exists()
    with SCOREBOARD.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SCOREBOARD_COLS)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in SCOREBOARD_COLS})
    print(f"\n  [harness] scoreboard updated → {SCOREBOARD}")


# ── Main evaluate() ───────────────────────────────────────────────────────────

def evaluate(
    pipeline_fn: Callable[[str, dict], dict],
    label: str,
    golden_path: Path = GOLDEN_PATH,
    sample_size: int | None = None,
) -> dict[str, Any]:
    """
    Run pipeline_fn on the golden set and record results.

    Args:
        pipeline_fn: function(question, filters) → {answer, retrieved_contexts, telemetry}
        label:       e.g. "v01_dense_only", "v02_hybrid", "v03_rerank"
        golden_path: path to golden_set.csv
        sample_size: if set, only evaluate this many rows (for quick checks)

    Returns:
        Full results dict including per-row scores.
    """
    golden = load_golden_set(golden_path)
    if sample_size:
        golden = golden[:sample_size]

    print(f"\n{'='*60}")
    print(f"  Evaluating: {label}")
    print(f"  Questions:  {len(golden)}")
    print(f"{'='*60}\n")

    questions:    list[str]       = []
    answers:      list[str]       = []
    contexts:     list[list[str]] = []
    ground_truths:list[str]       = []
    latencies:    list[float]     = []
    q_types:      list[str]       = []

    import esg_rag.albert as albert
    calls_before = albert.cost_summary().get("total_calls", 0)

    for i, row in enumerate(golden):
        print(f"  [{i+1:02d}/{len(golden)}] {row['question_type']:20} {row['question'][:60]}")
        t0 = time.perf_counter()

        try:
            result = pipeline_fn(row["question"], row["doc_filter"])
            answer   = result.get("answer", "")
            ctx_list = result.get("retrieved_contexts", [])
            latency  = result.get("telemetry", {}).get("latency_ms", 0)
        except Exception as e:
            print(f"    ERROR: {e}")
            answer   = f"ERROR: {e}"
            ctx_list = []
            latency  = (time.perf_counter() - t0) * 1000

        questions.append(row["question"])
        answers.append(answer)
        contexts.append(ctx_list[:6])   # RAGAS uses up to 6 contexts
        ground_truths.append(row["ground_truth_answer"])
        latencies.append(latency)
        q_types.append(row["question_type"])

        print(f"       → {len(ctx_list)} chunks  {latency:.0f}ms  "
              f"answer={answer[:80].replace(chr(10), ' ')}…")

    # ── Run metrics
    print(f"\n  Running RAGAS metrics on {len(questions)} questions…")
    metrics = _run_ragas(questions, answers, contexts, ground_truths)
    per_row = metrics.pop("_per_row", [{}] * len(questions))

    # ── Per-class slicing
    by_class_faith: dict[str, list[float]] = defaultdict(list)
    by_class_prec:  dict[str, list[float]] = defaultdict(list)
    for qt, row_m in zip(q_types, per_row):
        by_class_faith[qt].append(row_m.get("faithfulness", 0))
        by_class_prec[qt].append(row_m.get("context_precision", 0))

    faith_by_class = {
        k: round(sum(v) / len(v), 4) for k, v in by_class_faith.items()
    }
    prec_by_class = {
        k: round(sum(v) / len(v), 4) for k, v in by_class_prec.items()
    }

    # ── Albert call delta
    calls_after  = albert.cost_summary().get("total_calls", 0)
    avg_calls    = round((calls_after - calls_before) / len(questions), 1)
    avg_latency  = round(sum(latencies) / len(latencies), 1)

    scoreboard_row = {
        "config_id":                str(uuid.uuid4())[:8],
        "label":                    label,
        "timestamp":                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "faithfulness":             metrics["faithfulness"],
        "answer_relevancy":         metrics["answer_relevancy"],
        "context_precision":        metrics["context_precision"],
        "context_recall":           metrics["context_recall"],
        "faithfulness_by_class":    json.dumps(faith_by_class),
        "context_precision_by_class": json.dumps(prec_by_class),
        "avg_albert_calls":         avg_calls,
        "avg_latency_ms":           avg_latency,
        "n_questions":              len(questions),
    }

    _append_scoreboard(scoreboard_row)

    # ── Print summary
    print(f"\n{'='*60}")
    print(f"  Results for: {label}")
    print(f"  faithfulness:      {metrics['faithfulness']:.3f}")
    print(f"  answer_relevancy:  {metrics['answer_relevancy']:.3f}")
    print(f"  context_precision: {metrics['context_precision']:.3f}")
    print(f"  context_recall:    {metrics['context_recall']:.3f}")
    print(f"  avg_latency_ms:    {avg_latency:.0f}")
    print(f"  avg_albert_calls:  {avg_calls}")
    print(f"\n  By class — faithfulness:")
    for cls, val in faith_by_class.items():
        print(f"    {cls:25} {val:.3f}")
    print(f"{'='*60}\n")

    return {**scoreboard_row, "per_row": per_row}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run eval harness")
    parser.add_argument("--label",   required=True, help="e.g. v01_dense_only")
    parser.add_argument("--config",  default="pipeline_config.yaml")
    parser.add_argument("--sample",  type=int, default=None, help="Subset of golden set")
    parser.add_argument("--golden",  default=str(GOLDEN_PATH))
    args = parser.parse_args()

    import yaml as _yaml
    cfg = _yaml.safe_load(Path(args.config).read_text()) if Path(args.config).exists() else {}

    from esg_rag.synthesize import answer_question

    def pipeline_fn(question: str, filters: dict) -> dict:
        return answer_question(question, filters=filters, config=cfg)

    evaluate(
        pipeline_fn=pipeline_fn,
        label=args.label,
        golden_path=Path(args.golden),
        sample_size=args.sample,
    )
